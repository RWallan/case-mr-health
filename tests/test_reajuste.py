"""Reajuste do modelo servido na série estendida (#29, ADR 0011).

Seam 2: MLflow temporário e uma base consolidada sintética. O algoritmo
`naive` prevê o último valor, o que mostra se a série nova foi usada.
"""

import json
from datetime import date, timedelta

import duckdb
import mlflow
import numpy as np
import pytest
from mlflow import MlflowClient

from case_mr_health import algoritmos, intervalos
from case_mr_health.api.mlflow_cliente import SemVersao
from case_mr_health.config import Settings
from case_mr_health.intervalos import ConfigIntervalos
from case_mr_health.reajuste import reajustar_serie
from case_mr_health.treino import nome_modelo
from tests.test_api_predicao import registrar

CONFIG = ConfigIntervalos((0.80, 0.95), max_origens=5)
ULTIMO_NOVO = 77.0
ULTIMO_ANTIGO = 11.0
FIM_DIARIA = date(2021, 9, 10)
ULTIMA_SEGUNDA = date(2021, 9, 6)
HORIZONTE = {'diaria': 14, 'semanal': 2}
HASH = 'a' * 64
HP_SARIMA = {'ordem': [0, 0, 0], 'ordem_sazonal': [1, 0, 0, 7]}


def _y(n: int, ultimo: float) -> np.ndarray:
    rng = np.random.default_rng(n)
    return np.array([*rng.integers(1, 40, n - 1).astype(float), ultimo])


def _base(
    raiz, series: dict[tuple[str, str], np.ndarray]
) -> duckdb.DuckDBPyConnection:
    caminho = raiz / 'base.duckdb'
    with duckdb.connect(str(caminho)) as con:
        con.execute(
            'CREATE TABLE serie_diaria (sku VARCHAR, data DATE, '
            'quantidade DOUBLE, imputado BOOLEAN)'
        )
        con.execute(
            'CREATE TABLE serie_semanal (sku VARCHAR, semana DATE, '
            'quantidade DOUBLE)'
        )
        for (sku, gran), y in series.items():
            passo = timedelta(days=1 if gran == 'diaria' else 7)
            fim = FIM_DIARIA if gran == 'diaria' else ULTIMA_SEGUNDA
            for i, q in enumerate(y):
                dia = fim - passo * (len(y) - 1 - i)
                if gran == 'diaria':
                    con.execute(
                        'INSERT INTO serie_diaria VALUES (?, ?, ?, false)',
                        [sku, dia, float(q)],
                    )
                else:
                    con.execute(
                        'INSERT INTO serie_semanal VALUES (?, ?, ?)',
                        [sku, dia, float(q)],
                    )
    return caminho


@pytest.fixture
def cfg(tmp_path) -> Settings:
    series = {
        ('item A', 'diaria'): _y(40, ULTIMO_NOVO),
        ('item A', 'semanal'): _y(10, ULTIMO_NOVO),
        ('item B', 'diaria'): _y(60, ULTIMO_NOVO),
    }
    return Settings(
        _env_file=None,
        db_path=_base(tmp_path, series),
        mlflow_tracking_uri=f'sqlite:///{tmp_path / "mlflow.db"}',
        mlflow_artifact_dir=tmp_path / 'artefatos',
        modelos_fixados={},
    )


def _original(  # noqa: PLR0913, PLR0917
    cfg, sku, gran, algoritmo='naive', hp=None, **kwargs
):
    """Versão servida antes da atualização, com as tags que o treino grava."""
    hp = hp or {}
    y = _y(30 if algoritmo == 'naive' else 60, ULTIMO_ANTIGO)
    previsor = algoritmos.criar(algoritmo, hp, 1).ajustar(y)
    metodo_nativo = algoritmo == 'sarima'
    calibracao = (
        intervalos.nativa(CONFIG.niveis, HORIZONTE[gran], y)
        if metodo_nativo
        else intervalos.calibrar(
            lambda: algoritmos.criar(algoritmo, hp, 1),
            y,
            HORIZONTE[gran],
            CONFIG,
        )
    )
    registrado = registrar(
        cfg,
        sku,
        gran,
        previsor,
        calibracao,
        tags_run={'algoritmo': algoritmo},
        tags_versao={
            'algoritmo': algoritmo,
            'hiperparametros': json.dumps(hp),
            'intervalo_metodo': calibracao.metodo,
        },
        **kwargs,
    )
    MlflowClient().log_param(registrado.run_id, 'seed', 1)
    return registrado


def _versao(cfg, sku, gran, versao):
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    return MlflowClient().get_model_version(nome_modelo(sku, gran), versao)


def _champion(cfg, sku, gran) -> str:
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    versao = MlflowClient().get_model_version_by_alias(
        nome_modelo(sku, gran), 'champion'
    )
    return str(versao.version)


@pytest.mark.parametrize('gran', ['diaria', 'semanal'])
def test_registra_nova_versao_com_rastreabilidade(cfg, gran):
    antiga = _original(cfg, 'item A', gran)

    r = reajustar_serie(cfg, 'item A', gran, HASH)

    versao = _versao(cfg, 'item A', gran, r.versao_nova)
    assert r.versao_nova != antiga.versao
    assert r.versao_anterior == antiga.versao
    assert versao.tags['origem'] == 'atualizacao'
    assert versao.tags['versao_anterior'] == antiga.versao
    assert versao.tags['hash_dados'] == HASH
    assert versao.tags['hash_artefato'] == r.hash_artefato
    assert versao.tags['algoritmo'] == 'naive'


def test_champion_passa_para_a_versao_nova(cfg):
    _original(cfg, 'item A', 'diaria')

    r = reajustar_serie(cfg, 'item A', 'diaria', HASH)

    assert r.promovida
    assert _champion(cfg, 'item A', 'diaria') == r.versao_nova


def test_modelo_novo_enxerga_a_serie_estendida(cfg):
    _original(cfg, 'item A', 'diaria')

    r = reajustar_serie(cfg, 'item A', 'diaria', HASH)

    modelo = mlflow.pyfunc.load_model(
        f'models:/{nome_modelo("item A", "diaria")}/{r.versao_nova}'
    )
    previsto = modelo.unwrap_python_model().prever_com_intervalos(
        HORIZONTE['diaria']
    )
    assert len(previsto) == HORIZONTE['diaria']
    assert previsto['previsao'].tolist() == [ULTIMO_NOVO] * 14
    assert {'inferior_80', 'superior_95'} <= set(previsto.columns)


@pytest.mark.parametrize(
    ('gran', 'fim'),
    [('diaria', FIM_DIARIA), ('semanal', ULTIMA_SEGUNDA + timedelta(days=6))],
)
def test_desenvolvimento_fim_e_o_fim_da_serie_nova(cfg, gran, fim):
    _original(cfg, 'item A', gran)

    r = reajustar_serie(cfg, 'item A', gran, HASH)

    run = MlflowClient().get_run(
        _versao(cfg, 'item A', gran, r.versao_nova).run_id
    )
    assert r.desenvolvimento_fim == fim
    assert run.data.params['desenvolvimento_fim'] == str(fim)
    assert 'oot_fim' not in run.data.params


def test_versao_fixada_nao_muda_o_champion(cfg):
    antiga = _original(cfg, 'item A', 'diaria')
    fixada = cfg.model_copy(
        update={
            'modelos_fixados': {nome_modelo('item A', 'diaria'): antiga.versao}
        }
    )

    r = reajustar_serie(fixada, 'item A', 'diaria', HASH)

    assert not r.promovida
    assert _champion(cfg, 'item A', 'diaria') == antiga.versao


def test_mesmo_algoritmo_hiperparametros_e_metodo_de_intervalo(cfg):
    _original(cfg, 'item B', 'diaria', 'sarima', HP_SARIMA)

    r = reajustar_serie(cfg, 'item B', 'diaria', HASH)

    versao = _versao(cfg, 'item B', 'diaria', r.versao_nova)
    assert versao.tags['algoritmo'] == 'sarima'
    assert json.loads(versao.tags['hiperparametros']) == HP_SARIMA
    assert versao.tags['intervalo_metodo'] == intervalos.NATIVO


def test_reajustes_encadeados_apontam_para_a_versao_anterior(cfg):
    _original(cfg, 'item A', 'diaria')
    primeira = reajustar_serie(cfg, 'item A', 'diaria', HASH)

    segunda = reajustar_serie(cfg, 'item A', 'diaria', 'b' * 64)

    assert segunda.versao_anterior == primeira.versao_nova
    assert _champion(cfg, 'item A', 'diaria') == segunda.versao_nova


def test_serie_sem_versao_servida_nao_e_reajustada(cfg):
    with pytest.raises(SemVersao):
        reajustar_serie(cfg, 'item A', 'diaria', HASH)


def test_falha_nao_troca_a_versao_servida(cfg):
    # `item C` tem versão servida, mas nenhuma linha na base.
    antiga = _original(cfg, 'item C', 'diaria')

    with pytest.raises(ValueError, match='sem dados'):
        reajustar_serie(cfg, 'item C', 'diaria', HASH)

    assert _champion(cfg, 'item C', 'diaria') == antiga.versao
    versoes = MlflowClient().search_model_versions(
        f"name = '{nome_modelo('item C', 'diaria')}'"
    )
    assert len(versoes) == 1


def test_so_o_algoritmo_servido_e_ajustado(cfg, monkeypatch):
    _original(cfg, 'item A', 'diaria')
    criados = []
    criar = algoritmos.criar

    def registrar_criacao(nome, hp, seed):
        criados.append(nome)
        return criar(nome, hp, seed)

    monkeypatch.setattr(algoritmos, 'criar', registrar_criacao)

    reajustar_serie(cfg, 'item A', 'diaria', HASH)

    assert criados
    assert set(criados) == {'naive'}
