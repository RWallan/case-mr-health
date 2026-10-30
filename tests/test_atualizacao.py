"""Ingestão de pedidos novos (#28, ADR 0011), com planilhas sintéticas."""

import hashlib
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest
from openpyxl import Workbook

from case_mr_health.atualizacao import (
    HASH_INICIAL,
    AtualizacaoRepetidaError,
    hash_dados_atual,
    ingerir_pedidos,
)
from case_mr_health.dados import DadosInvalidosError, preparar_dados

PRIMEIRO_NOVO = 9_000_000_001
ITENS_CONSOLIDADOS = 3  # A somado e B no primeiro pedido, A no segundo
QUANTIDADE_A_SOMADA = 5
ATUALIZACOES = 3  # duas aplicadas e a base inicial


def _escrever(
    destino: Path, pedidos: list[tuple], itens: list[tuple]
) -> tuple[Path, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.append([None, 'ID_PEDIDO', 'DATA', 'VALOR_TOTAL'])
    for i, (id_pedido, data) in enumerate(pedidos):
        ws.append([i, id_pedido, data, None])
    wb.save(destino / 'novo_pedido.xlsx')
    wb = Workbook()
    ws = wb.active
    ws.append([None, 'ID_PEDIDO', 'ID_ITEM', 'QUANTIDADE'])
    for i, (id_pedido, sku, qtd) in enumerate(itens):
        ws.append([i, id_pedido, sku, qtd])
    wb.save(destino / 'novo_item.xlsx')
    return destino / 'novo_pedido.xlsx', destino / 'novo_item.xlsx'


@pytest.fixture
def base(settings):
    preparar_dados(settings)
    return settings


@pytest.fixture
def novos(tmp_path, planilhas):
    """Dois pedidos novos depois do fim da base, um com SKU repetido."""
    fim = max(date.fromisoformat(d) for _, d in planilhas.pedidos)
    dia1, dia2 = fim + timedelta(days=3), fim + timedelta(days=4)
    pedidos = [
        (PRIMEIRO_NOVO, f'{dia1:%Y-%m-%d}'),
        (PRIMEIRO_NOVO + 1, f'{dia2:%Y-%m-%d}'),
    ]
    itens = [
        (PRIMEIRO_NOVO, 'item A', 2),
        (PRIMEIRO_NOVO, 'item A', 3),
        (PRIMEIRO_NOVO, 'item B', 1),
        (PRIMEIRO_NOVO + 1, 'item A', 4),
    ]
    return pedidos, itens, dia1, dia2, fim


def _contagens(cfg) -> dict[str, int]:
    with duckdb.connect(str(cfg.db_path), read_only=True) as con:
        return {
            t: con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
            for t in ('pedido', 'item_pedido', 'base_consolidada')
        }


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_acrescenta_apenas_os_pedidos_novos(base, novos, tmp_path):
    pedidos, itens, *_ = novos
    antes = _contagens(base)
    arquivos = _escrever(tmp_path / 'novos', pedidos, itens)

    ingestao = ingerir_pedidos(base, *arquivos)

    depois = _contagens(base)
    assert ingestao.pedidos_novos == len(pedidos)
    assert ingestao.itens_novos == ITENS_CONSOLIDADOS
    assert depois['pedido'] == antes['pedido'] + 2
    assert depois['item_pedido'] == antes['item_pedido'] + ITENS_CONSOLIDADOS
    assert depois['base_consolidada'] == (
        antes['base_consolidada'] + ITENS_CONSOLIDADOS
    )


def test_itens_repetidos_do_pedido_sao_somados(base, novos, tmp_path):
    pedidos, itens, *_ = novos

    ingerir_pedidos(base, *_escrever(tmp_path / 'n', pedidos, itens))

    with duckdb.connect(str(base.db_path), read_only=True) as con:
        quantidade = con.execute(
            'SELECT quantidade FROM item_pedido '
            "WHERE id_pedido = ? AND sku = 'item A'",
            [PRIMEIRO_NOVO],
        ).fetchone()[0]
        valor_pedido = con.execute(
            'SELECT valor_total FROM pedido WHERE id_pedido = ?',
            [PRIMEIRO_NOVO],
        ).fetchone()[0]
        precos = dict(
            con.execute('SELECT sku, valor_unitario FROM sku').fetchall()
        )
    assert quantidade == QUANTIDADE_A_SOMADA
    assert (
        valor_pedido
        == QUANTIDADE_A_SOMADA * precos['item A'] + 1 * precos['item B']
    )


def test_series_sao_reconstruidas_ate_o_novo_ultimo_dia(base, novos, tmp_path):
    pedidos, itens, dia1, dia2, fim = novos

    ingestao = ingerir_pedidos(
        base, *_escrever(tmp_path / 'n', pedidos, itens)
    )

    assert ingestao.ultimo_dia == dia2
    with duckdb.connect(str(base.db_path), read_only=True) as con:
        diaria = dict(
            con.execute(
                'SELECT data, quantidade FROM serie_diaria '
                "WHERE sku = 'item A' AND data > ?",
                [fim],
            ).fetchall()
        )
    esperado = defaultdict(int, {dia1: 5, dia2: 4})
    assert {d: diaria.get(d, 0) for d in (dia1, dia2)} == {
        d: esperado[d] for d in (dia1, dia2)
    }
    assert max(diaria) == dia2


def test_pedido_ja_existente_e_recusado_com_a_linha(
    base, novos, tmp_path, planilhas
):
    pedidos, itens, *_ = novos
    existente = planilhas.pedidos[0][0]
    pedidos = [(existente, pedidos[0][1]), *pedidos[1:]]
    itens = [
        (existente, *i[1:]) if i[0] == PRIMEIRO_NOVO else i for i in itens
    ]
    antes = _contagens(base)

    with pytest.raises(DadosInvalidosError, match='PEDIDO linha 2') as erro:
        ingerir_pedidos(base, *_escrever(tmp_path / 'n', pedidos, itens))

    assert 'já existe na base' in str(erro.value)
    assert _contagens(base) == antes


def test_erro_de_item_aponta_a_linha_e_nao_altera_a_base(
    base, novos, tmp_path
):
    pedidos, itens, *_ = novos
    itens = [*itens[:2], (PRIMEIRO_NOVO, 'item Z', 1), *itens[2:]]
    antes = _contagens(base)

    with pytest.raises(
        DadosInvalidosError, match=r'ITEM_PEDIDO linha 4: SKU .item Z.'
    ):
        ingerir_pedidos(base, *_escrever(tmp_path / 'n', pedidos, itens))

    assert _contagens(base) == antes
    assert hash_dados_atual(base) == HASH_INICIAL


@pytest.mark.parametrize(
    ('item', 'trecho'),
    [
        ((PRIMEIRO_NOVO, 'item A', -1), 'quantidade negativa'),
        ((PRIMEIRO_NOVO, 'item A', 1.5), 'quantidade não inteira'),
        ((PRIMEIRO_NOVO + 7, 'item A', 1), 'sem registro em PEDIDO'),
    ],
)
def test_itens_invalidos_sao_recusados(base, novos, tmp_path, item, trecho):
    pedidos, itens, *_ = novos

    with pytest.raises(DadosInvalidosError, match=trecho):
        ingerir_pedidos(
            base, *_escrever(tmp_path / 'n', pedidos, [*itens, item])
        )


def test_data_invalida_e_recusada(base, novos, tmp_path):
    pedidos, itens, *_ = novos
    pedidos = [(pedidos[0][0], '30/09/2021'), pedidos[1]]

    with pytest.raises(DadosInvalidosError, match='PEDIDO linha 2: data'):
        ingerir_pedidos(base, *_escrever(tmp_path / 'n', pedidos, itens))


def test_cabecalho_inesperado_e_recusado(base, novos, tmp_path):
    pedidos, itens, *_ = novos
    pedido, item = _escrever(tmp_path / 'n', pedidos, itens)

    with pytest.raises(DadosInvalidosError, match='Cabeçalho inesperado'):
        ingerir_pedidos(base, item, pedido)


def test_mesmo_par_de_arquivos_nao_e_aplicado_duas_vezes(
    base, novos, tmp_path
):
    pedidos, itens, *_ = novos
    arquivos = _escrever(tmp_path / 'n', pedidos, itens)
    ingerir_pedidos(base, *arquivos)
    antes = _contagens(base)

    with pytest.raises(AtualizacaoRepetidaError):
        ingerir_pedidos(base, *arquivos)

    assert _contagens(base) == antes


def test_hash_dos_dados_encadeia_as_atualizacoes(base, novos, tmp_path):
    pedidos, itens, dia1, dia2, _ = novos
    assert hash_dados_atual(base) == HASH_INICIAL

    primeira = ingerir_pedidos(
        base, *_escrever(tmp_path / 'a', pedidos[:1], itens[:3])
    )
    assert hash_dados_atual(base) == primeira.hash_dados
    segunda = ingerir_pedidos(
        base, *_escrever(tmp_path / 'b', pedidos[1:], itens[3:])
    )

    assert hash_dados_atual(base) == segunda.hash_dados
    assert (
        len({primeira.hash_dados, segunda.hash_dados, HASH_INICIAL})
        == ATUALIZACOES
    )


def test_guarda_copia_dos_arquivos_aplicados(base, novos, tmp_path):
    pedidos, itens, *_ = novos
    base = base.model_copy(update={'atualizacoes_dir': tmp_path / 'copias'})

    ingestao = ingerir_pedidos(
        base, *_escrever(tmp_path / 'n', pedidos, itens)
    )

    pasta = tmp_path / 'copias' / ingestao.hash_dados
    assert _sha(pasta / 'pedido.xlsx') == ingestao.hash_pedido
    assert _sha(pasta / 'item_pedido.xlsx') == ingestao.hash_itens


def test_visao_de_desenvolvimento_e_oot_nao_sao_tocados(base, novos, tmp_path):
    pedidos, itens, *_ = novos
    antes = (_sha(base.desenvolvimento_db_path), _sha(base.oot_db_path))

    ingerir_pedidos(base, *_escrever(tmp_path / 'n', pedidos, itens))

    assert antes == (
        _sha(base.desenvolvimento_db_path),
        _sha(base.oot_db_path),
    )
