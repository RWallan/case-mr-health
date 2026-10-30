"""Avaliação final no OOT (#13): portões, tentativa única e promoção.

O mundo é sintético: MLflow temporário, visão de desenvolvimento e OOT em
DuckDB temporários e um `.ds-workflow` mínimo. O OOT real nunca é aberto.
"""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow import MlflowClient

from case_mr_health import algoritmos, avaliacao_final, intervalos
from case_mr_health.avaliacao_final import (
    ARTEFATO_GRAFICO_OOT,
    cobertura,
    decisoes_aprovadas,
    medir,
    promover,
    registrar_tentativa,
    verificar_gates,
)
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.intervalos import ConfigIntervalos
from case_mr_health.particoes import GRANULARIDADES
from case_mr_health.selecao import ALIAS_SELECIONADO
from case_mr_health.treino import nome_modelo
from tests.test_api_predicao import registrar

CONFIG = ConfigIntervalos((0.80, 0.95), max_origens=5)
FIM_DIARIA = date(2021, 8, 15)
FIM_SEMANAL = date(2021, 8, 15)
ULTIMA_SEMANA = date(2021, 8, 9)
OOT_INICIO = date(2021, 8, 16)
HORIZONTE = {'diaria': 14, 'semanal': 2}
ULTIMO = 10.0
PROTOCOLO = Path('docs/analysis/protocolo-avaliacao-final.md')


# --- política de dados ------------------------------------------------------


def _evento(i: str, evento: str, kind: str | None = None) -> str:
    dados = {'id': i, 'event': evento}
    if kind:
        dados['kind'] = kind
    return json.dumps(dados)


def _politica(
    raiz: Path,
    *,
    fase='final_evaluation',
    aprovadas=('D-019', 'D-020', 'D-021'),
    congelar=True,
    protocolo='texto do protocolo',
) -> None:
    (raiz / PROTOCOLO).parent.mkdir(parents=True, exist_ok=True)
    (raiz / PROTOCOLO).write_text(protocolo, encoding='utf-8')
    sha = hashlib.sha256(b'texto do protocolo').hexdigest()
    estado = {'phase': fase, 'frozen': {}}
    if congelar:
        estado['frozen']['evaluation_protocol'] = {'sha256': sha}
    (raiz / '.ds-workflow').mkdir(exist_ok=True)
    (raiz / '.ds-workflow/state.json').write_text(json.dumps(estado))
    tipos = {
        'D-019': 'model_selection',
        'D-020': 'conclusion',
        'D-021': 'final_evaluation',
        'D-022': 'recommendation',
    }
    linhas = [_evento(i, 'proposed', k) for i, k in tipos.items()]
    linhas += [_evento(i, 'approved') for i in aprovadas]
    (raiz / '.ds-workflow/decisions.jsonl').write_text('\n'.join(linhas))


def test_gates_cumpridos(tmp_path):
    _politica(tmp_path)

    verificar_gates(tmp_path)


@pytest.mark.parametrize(
    ('ajuste', 'trecho'),
    [
        ({'fase': 'modeling'}, 'final_evaluation'),
        ({'congelar': False}, 'não congelado'),
        ({'aprovadas': ('D-020', 'D-021')}, 'D-019 não aprovada'),
        ({'aprovadas': ('D-019', 'D-021')}, 'D-020 não aprovada'),
        ({'aprovadas': ('D-019', 'D-020')}, 'sem decisão final_evaluation'),
    ],
)
def test_gate_nao_cumprido_aborta(tmp_path, ajuste, trecho):
    _politica(tmp_path, **ajuste)

    with pytest.raises(ValueError, match=trecho):
        verificar_gates(tmp_path)


def test_protocolo_alterado_depois_de_congelado_aborta(tmp_path):
    _politica(tmp_path, protocolo='outro texto')

    with pytest.raises(ValueError, match='protocolo mudou'):
        verificar_gates(tmp_path)


def test_decisao_rejeitada_depois_de_aprovada_nao_vale(tmp_path):
    _politica(tmp_path)
    with (tmp_path / '.ds-workflow/decisions.jsonl').open('a') as arquivo:
        arquivo.write('\n' + _evento('D-019', 'rejected'))

    assert 'D-019' not in decisoes_aprovadas(tmp_path)


def test_gate_nao_cumprido_nao_abre_o_oot(tmp_path, monkeypatch):
    _politica(tmp_path, fase='modeling')
    monkeypatch.setattr(
        avaliacao_final,
        'ler_oot',
        lambda *_: pytest.fail('o OOT foi aberto'),
    )

    with pytest.raises(ValueError, match='Portões'):
        avaliacao_final.avaliar_final(Settings(_env_file=None), tmp_path)

    assert not (
        tmp_path / '.ds-workflow/final-evaluation-attempt.json'
    ).exists()


def test_tentativa_so_pode_ser_marcada_uma_vez(tmp_path):
    marca = tmp_path / '.ds-workflow/tentativa.json'
    registrar_tentativa(marca)

    with pytest.raises(ValueError, match='já foi iniciada'):
        registrar_tentativa(marca)


# --- métricas ---


def test_cobertura_tem_limites_inclusivos():
    obtida = cobertura([1, 2, 3, 9], [1, 2, 4, 0], [1, 5, 5, 8])

    assert obtida == pytest.approx(0.5)


def test_cobertura_sem_limites_e_indefinida():
    assert np.isnan(cobertura([1.0], [np.nan], [np.nan]))


def test_medir_usa_a_escala_dada():
    previsto = pd.DataFrame({
        'previsao': [10.0, 10.0],
        'inferior_80': [9.0, 9.0],
        'superior_80': [11.0, 11.0],
        'inferior_95': [8.0, 8.0],
        'superior_95': [12.0, 12.0],
    })

    medidas, cobertas = medir([10.0, 12.0], previsto, escala=2.0)

    assert medidas['mae'] == pytest.approx(1.0)
    assert medidas['mse'] == pytest.approx(2.0)
    assert medidas['rmse'] == pytest.approx(np.sqrt(2.0))
    assert medidas['wape'] == pytest.approx(2 / 22)
    assert medidas['mase'] == pytest.approx(0.5)
    assert cobertas == {80: 0.5, 95: 1.0}


# --- mundo sintético ------------------------------------------------------


def _y(granularidade: str) -> np.ndarray:
    rng = np.random.default_rng(len(granularidade))
    return np.array([*rng.integers(1, 40, 29).astype(float), ULTIMO])


def _observado(granularidade: str) -> list[float]:
    if granularidade == 'diaria':
        return [ULTIMO] * 7 + [ULTIMO + 2] * 7
    return [ULTIMO, ULTIMO + 2]


def _criar_bancos(raiz: Path) -> tuple[Path, Path]:
    dev, oot = raiz / 'dev.duckdb', raiz / 'oot.duckdb'
    with duckdb.connect(str(dev)) as con:
        con.execute(
            'CREATE TABLE serie_diaria '
            '(sku VARCHAR, data DATE, quantidade DOUBLE, imputado BOOLEAN)'
        )
        con.execute(
            'CREATE TABLE serie_semanal '
            '(sku VARCHAR, semana DATE, quantidade DOUBLE)'
        )
        con.execute(
            'CREATE TABLE particao (sku VARCHAR, granularidade VARCHAR, '
            'desenvolvimento_inicio DATE, desenvolvimento_fim DATE, '
            'oot_inicio DATE, oot_fim DATE)'
        )
        con.execute(
            'CREATE TABLE fold (sku VARCHAR, granularidade VARCHAR, '
            'fold INTEGER, treino_inicio DATE, treino_fim DATE, '
            'teste_inicio DATE, teste_fim DATE)'
        )
    with duckdb.connect(str(oot)) as con:
        con.execute(
            'CREATE TABLE serie_diaria '
            '(sku VARCHAR, data DATE, quantidade DOUBLE, imputado BOOLEAN)'
        )
        con.execute(
            'CREATE TABLE serie_semanal '
            '(sku VARCHAR, semana DATE, quantidade DOUBLE)'
        )
    for sku in SKUS:
        for gran in GRANULARIDADES:
            _preencher(dev, oot, sku, gran)
    return dev, oot


def _preencher(dev: Path, oot: Path, sku: str, gran: str) -> None:
    y = _y(gran)
    passo = timedelta(days=1 if gran == 'diaria' else 7)
    fim = FIM_DIARIA if gran == 'diaria' else ULTIMA_SEMANA
    datas = [fim - passo * (len(y) - 1 - i) for i in range(len(y))]
    tabela, coluna = (
        ('serie_diaria', 'data')
        if gran == 'diaria'
        else ('serie_semanal', 'semana')
    )
    marcas = '(?, ?, ?, false)' if gran == 'diaria' else '(?, ?, ?)'
    with duckdb.connect(str(dev)) as con:
        con.executemany(
            f'INSERT INTO {tabela} VALUES {marcas}',
            [[sku, d, float(q)] for d, q in zip(datas, y, strict=True)],
        )
        con.execute(
            'INSERT INTO particao VALUES (?, ?, ?, ?, ?, ?)',
            [
                sku,
                gran,
                datas[0],
                FIM_DIARIA,
                OOT_INICIO,
                OOT_INICIO + passo * (HORIZONTE[gran] - 1)
                if gran == 'diaria'
                else date(2021, 8, 23) + timedelta(days=6),
            ],
        )
    with duckdb.connect(str(oot)) as con:
        con.executemany(
            f'INSERT INTO {tabela} VALUES {marcas}',
            [
                [sku, OOT_INICIO + passo * i, q]
                for i, q in enumerate(_observado(gran))
            ],
        )


@pytest.fixture(scope='module')
def mundo(tmp_path_factory):
    raiz = tmp_path_factory.mktemp('avaliacao_final')
    dev, oot = _criar_bancos(raiz)
    cfg = Settings(
        _env_file=None,
        mlflow_tracking_uri=f'sqlite:///{raiz / "mlflow.db"}',
        mlflow_artifact_dir=raiz / 'artefatos',
        desenvolvimento_db_path=dev,
        oot_db_path=oot,
        historico_db_path=raiz / 'h.duckdb',
    )
    versoes = {}
    for sku in SKUS:
        for gran in GRANULARIDADES:
            y = _y(gran)
            previsor = algoritmos.criar('naive', {}, 1).ajustar(y)
            calibracao = intervalos.calibrar(
                lambda: algoritmos.criar('naive', {}, 1),
                y,
                HORIZONTE[gran],
                CONFIG,
            )
            registrado = registrar(
                cfg,
                sku,
                gran,
                previsor,
                calibracao,
                tags_versao={'algoritmo': 'naive'},
                champion=False,
            )
            cliente = MlflowClient()
            cliente.set_registered_model_alias(
                nome_modelo(sku, gran), ALIAS_SELECIONADO, registrado.versao
            )
            cliente.log_dict(registrado.run_id, {'folds': []}, 'backtest.json')
            versoes[sku, gran] = registrado
    _politica(raiz)
    return cfg, raiz, versoes


@pytest.fixture(scope='module')
def avaliado(mundo):
    cfg, raiz, _ = mundo
    relatorio = raiz / 'relatorio.md'
    resultados = avaliacao_final.avaliar_final(cfg, raiz, relatorio)
    return resultados, relatorio


# --- avaliação ---


def test_avalia_as_oito_series(avaliado):
    resultados, _ = avaliado

    assert {(r.sku, r.granularidade) for r in resultados} == {
        (s, g) for s in SKUS for g in GRANULARIDADES
    }


@pytest.mark.parametrize('granularidade', GRANULARIDADES)
def test_metricas_conferem_com_o_calculo_manual(avaliado, granularidade):
    resultados, _ = avaliado

    for r in (x for x in resultados if x.granularidade == granularidade):
        erros = np.abs(np.array(_observado(granularidade)) - ULTIMO)
        assert r.metricas['mae'] == pytest.approx(erros.mean())
        assert r.metricas['wape'] == pytest.approx(
            erros.sum() / sum(_observado(granularidade))
        )
        assert len(r.observado) == HORIZONTE[granularidade]


def test_metricas_e_cobertura_vao_para_o_mlflow(mundo, avaliado):
    _, _, versoes = mundo
    resultados, _ = avaliado
    cliente = MlflowClient()

    for r in resultados:
        run = cliente.get_run(versoes[r.sku, r.granularidade].run_id)
        assert run.data.tags['oot_avaliado'] == 'true'
        assert run.data.metrics['oot_mae'] == pytest.approx(r.metricas['mae'])
        assert 0 <= run.data.metrics['oot_cobertura_80'] <= 1
        assert 0 <= run.data.metrics['oot_cobertura_95'] <= 1


def test_grafico_e_dados_do_oot_ficam_no_run(mundo, avaliado):
    _, _, versoes = mundo
    cliente = MlflowClient()

    artefatos = {
        a.path
        for a in cliente.list_artifacts(versoes['item A', 'diaria'].run_id)
    }

    assert {ARTEFATO_GRAFICO_OOT, 'oot.json'} <= artefatos


def test_relatorio_tem_uma_linha_por_serie_e_as_limitacoes(avaliado):
    _, relatorio = avaliado

    texto = relatorio.read_text(encoding='utf-8')

    assert texto.count('| item ') == len(SKUS) * len(GRANULARIDADES)
    assert '2 pontos' in texto
    assert 'confiança' in texto


def test_avaliacao_nao_atribui_champion(mundo, avaliado):
    cfg, _, _ = mundo
    cliente = MlflowClient()

    for sku in SKUS:
        for gran in GRANULARIDADES:
            versao = cliente.get_model_version_by_alias(
                nome_modelo(sku, gran), ALIAS_SELECIONADO
            )
            assert 'champion' not in versao.aliases


def test_segunda_avaliacao_nao_abre_o_oot(mundo, avaliado, monkeypatch):
    cfg, raiz, _ = mundo
    monkeypatch.setattr(
        avaliacao_final,
        'ler_oot',
        lambda *_: pytest.fail('o OOT foi aberto de novo'),
    )

    with pytest.raises(ValueError, match='já foi iniciada'):
        avaliacao_final.avaliar_final(cfg, raiz)


def test_marca_da_tentativa_registra_a_conclusao(mundo, avaliado):
    _, raiz, _ = mundo

    marca = json.loads(
        (raiz / '.ds-workflow/final-evaluation-attempt.json').read_text()
    )

    assert marca['estado'] == 'concluida'


# --- promoção -------------------------------------------------------------


def test_promover_atribui_champion_com_decisao_aprovada(mundo, avaliado):
    cfg, raiz, versoes = mundo
    _politica(raiz, aprovadas=('D-019', 'D-020', 'D-021', 'D-022'))
    versao = versoes['item A', 'semanal'].versao

    promover(cfg, 'item A', 'semanal', versao, 'D-022', raiz)

    obtida = MlflowClient().get_model_version_by_alias(
        nome_modelo('item A', 'semanal'), 'champion'
    )
    assert str(obtida.version) == versao


def test_promover_exige_decisao_aprovada(mundo, avaliado):
    cfg, raiz, versoes = mundo
    _politica(raiz)

    with pytest.raises(ValueError, match='D-022 não está aprovada'):
        promover(
            cfg,
            'item B',
            'semanal',
            versoes['item B', 'semanal'].versao,
            'D-022',
            raiz,
        )

    with pytest.raises(mlflow.exceptions.MlflowException):
        MlflowClient().get_model_version_by_alias(
            nome_modelo('item B', 'semanal'), 'champion'
        )


def test_promover_recusa_versao_cujo_run_e_de_outra_serie(mundo, avaliado):
    cfg, raiz, versoes = mundo
    _politica(raiz, aprovadas=('D-019', 'D-020', 'D-021', 'D-022'))
    registrado = versoes['item D', 'semanal']
    MlflowClient().set_tag(registrado.run_id, 'sku', 'item C')

    with pytest.raises(ValueError, match='não é da série'):
        promover(cfg, 'item D', 'semanal', registrado.versao, 'D-022', raiz)


def test_promover_recusa_versao_nao_avaliada(mundo, avaliado):
    cfg, raiz, versoes = mundo
    _politica(raiz, aprovadas=('D-019', 'D-020', 'D-021', 'D-022'))
    y = _y('semanal')
    extra = registrar(
        cfg,
        'item C',
        'semanal',
        algoritmos.criar('naive', {}, 1).ajustar(y),
        intervalos.calibrar(
            lambda: algoritmos.criar('naive', {}, 1), y, 2, CONFIG
        ),
        champion=False,
    )

    with pytest.raises(ValueError, match='não passou pela avaliação'):
        promover(cfg, 'item C', 'semanal', extra.versao, 'D-022', raiz)
