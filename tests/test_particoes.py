from datetime import date, timedelta

import duckdb
import pytest

from case_mr_health.config import Settings
from case_mr_health.dados import preparar_dados
from case_mr_health.particoes import (
    abrir_desenvolvimento,
    carregar_particoes,
    particionar,
)
from tests.conftest import escrever_planilhas

HISTORICO = date(2021, 6, 1)
N_SERIES = 8  # 4 SKUs x 2 granularidades


def _dias(inicio: date, n: int) -> list[date]:
    return [inicio + timedelta(days=i) for i in range(n)]


def _semanas(inicio: date, n: int) -> list[date]:
    return [inicio + timedelta(weeks=i) for i in range(n)]


@pytest.fixture
def particoes(settings):
    preparar_dados(settings)
    return carregar_particoes(settings)


def test_particoes_por_serie_somam_8_series(particoes):
    series = {(p.sku, p.granularidade) for p in particoes}

    assert len(series) == len(particoes) == N_SERIES
    assert {g for _, g in series} == {'diaria', 'semanal'}


def test_particoes_sao_cronologicas_e_sem_sobreposicao(particoes):
    for p in particoes:
        assert p.desenvolvimento_inicio <= p.desenvolvimento_fim
        assert p.desenvolvimento_fim < p.oot_inicio <= p.oot_fim
        assert p.folds
        for anterior, atual in zip(p.folds, p.folds[1:], strict=False):
            assert atual.treino_inicio == anterior.treino_inicio
            assert atual.treino_fim == anterior.teste_fim
            assert atual.teste_inicio == anterior.teste_fim + timedelta(1)
        for f in p.folds:
            assert f.treino_inicio <= f.treino_fim < f.teste_inicio
            assert f.teste_inicio <= f.teste_fim <= p.desenvolvimento_fim


def test_tamanhos_vem_da_configuracao(particoes, settings):
    for p in particoes:
        oot = (p.oot_fim - p.oot_inicio).days + 1
        teste = (p.folds[0].teste_fim - p.folds[0].teste_inicio).days + 1
        treino = (p.folds[0].treino_fim - p.folds[0].treino_inicio).days + 1
        if p.granularidade == 'diaria':
            esperado = (
                settings.oot_diaria_dias,
                settings.fold_diaria_dias,
                settings.treino_minimo_diaria_dias,
            )
        else:
            esperado = tuple(
                7 * n
                for n in (
                    settings.oot_semanal_semanas,
                    settings.fold_semanal_semanas,
                    settings.treino_minimo_semanal_semanas,
                )
            )
        assert (oot, teste, treino) == esperado


def test_particionar_respeita_parametros_da_configuracao():
    cfg = Settings(
        oot_diaria_dias=7,
        fold_diaria_dias=3,
        treino_minimo_diaria_dias=20,
    )

    p = particionar('item A', 'diaria', _dias(HISTORICO, 60), cfg)

    assert p.oot_inicio == HISTORICO + timedelta(days=53)
    assert p.desenvolvimento_fim == HISTORICO + timedelta(days=52)
    assert p.folds[0].treino_fim == HISTORICO + timedelta(days=19)
    assert p.folds[0].teste_fim == HISTORICO + timedelta(days=22)
    assert len(p.folds) == (53 - 20) // 3


@pytest.mark.parametrize(
    ('periodos', 'granularidade', 'n_folds'),
    [(_dias(HISTORICO, 93), 'diaria', 5), (_dias(HISTORICO, 90), 'diaria', 4)]
    + [(_semanas(date(2021, 6, 7), 12), 'semanal', 4)],
)
def test_padroes_do_adr_0002_com_treino_minimo_de_42_dias(
    periodos, granularidade, n_folds
):
    p = particionar('item A', granularidade, periodos, Settings())

    assert len(p.folds) == n_folds


def test_serie_curta_demais_e_rejeitada():
    with pytest.raises(ValueError, match='sem períodos suficientes'):
        particionar('item A', 'diaria', _dias(HISTORICO, 50), Settings())


def test_visao_de_desenvolvimento_nao_tem_oot(particoes, settings):
    dev = abrir_desenvolvimento(settings)
    oot = duckdb.connect(str(settings.oot_db_path), read_only=True)
    try:
        for p in particoes:
            tabela, coluna = (
                ('serie_diaria', 'data')
                if p.granularidade == 'diaria'
                else ('serie_semanal', 'semana')
            )
            consulta = (
                f'SELECT min({coluna}), max({coluna}) FROM {tabela} '
                f"WHERE sku = '{p.sku}'"
            )
            assert dev.execute(consulta).fetchone() == (
                p.desenvolvimento_inicio,
                p.desenvolvimento_fim - timedelta(days=6)
                if p.granularidade == 'semanal'
                else p.desenvolvimento_fim,
            )
            minimo_oot = oot.execute(consulta).fetchone()[0]
            assert minimo_oot == p.oot_inicio
    finally:
        dev.close()
        oot.close()


def _conteudo_desenvolvimento(settings, granularidade):
    tabela = 'serie_diaria' if granularidade == 'diaria' else 'serie_semanal'
    con = abrir_desenvolvimento(settings)
    try:
        return {
            consulta: con.execute(consulta).fetchall()
            for consulta in (
                f'SELECT * FROM {tabela} ORDER BY ALL',
                'SELECT * FROM particao '
                f"WHERE granularidade = '{granularidade}' ORDER BY ALL",
                'SELECT * FROM fold '
                f"WHERE granularidade = '{granularidade}' ORDER BY ALL",
            )
        }
    finally:
        con.close()


@pytest.mark.parametrize('granularidade', ['diaria', 'semanal'])
def test_alterar_o_oot_nao_muda_a_visao_de_desenvolvimento(
    settings, planilhas, granularidade
):
    """Vale por granularidade: a visão diária contém dias que pertencem
    às semanas do OOT semanal (limitação aceita, ADR 0002 / ticket #4)."""
    preparar_dados(settings)
    antes = _conteudo_desenvolvimento(settings, granularidade)
    inicio_oot = min(
        p.oot_inicio
        for p in carregar_particoes(settings)
        if p.granularidade == granularidade
    )
    em_oot = {
        id_pedido
        for id_pedido, data in planilhas.pedidos
        if date.fromisoformat(data) >= inicio_oot
    }
    assert em_oot
    itens = [
        (id_pedido, sku, qtd + 3 if id_pedido in em_oot else qtd)
        for id_pedido, sku, qtd in planilhas.itens
    ]
    escrever_planilhas(
        planilhas.raw_dir, planilhas.pedidos, itens, planilhas.precos
    )

    preparar_dados(settings)

    assert _conteudo_desenvolvimento(settings, granularidade) == antes
