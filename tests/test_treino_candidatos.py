import json
from dataclasses import replace
from importlib import metadata
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow import MlflowClient

from case_mr_health import algoritmos, treino
from case_mr_health.algoritmos_statsmodels import (
    DiagnosticoAjuste,
    FalhaConvergencia,
    publicar_diagnostico,
)
from case_mr_health.candidatos import NAO_TESTAVEL
from case_mr_health.config import Settings
from case_mr_health.treino import (
    carregar_serie,
    requisitos_pip,
    treinar_serie,
)
from tests.test_treino import (
    N_DIAS,
    PADROES,
    _gravar_origem,
    _particao,
    _por_algoritmo,
)

HORIZONTE = 7
RUNS_SEMANAIS = 3  # naive, média e SES
INTERMITENTES = ('croston', 'sba', 'tsb')
PROPHET = {'ordem_fourier': 2, 'escala_sazonalidade': 1.0}
VENDAS = np.random.default_rng(20261030).poisson(
    [1, 1, 2, 2, 6, 7, 5] * (N_DIAS // 7)
)


def _vendas(i):
    return int(VENDAS[i])


@pytest.fixture
def cfg(tmp_path) -> Settings:
    cfg = Settings(
        db_path=tmp_path / 'origem.duckdb',
        desenvolvimento_db_path=tmp_path / 'dev.duckdb',
        oot_db_path=tmp_path / 'fora.duckdb',
        mlflow_tracking_uri=f'sqlite:///{tmp_path / "mlflow.db"}',
        mlflow_artifact_dir=tmp_path / 'artefatos',
    )
    # O item D de `PADROES` tem soma semanal constante; aqui ele varia.
    _gravar_origem(cfg, {**PADROES, 'item D': _vendas})
    return cfg


@pytest.fixture
def so_estes(monkeypatch):
    """Reduz o registro aos pedidos e reativa os cortados da tabela."""

    def restringir(*nomes):
        monkeypatch.setattr(
            algoritmos,
            'ALGORITMOS',
            {n: algoritmos.ALGORITMOS[n] for n in nomes},
        )
        tabela = treino.candidatos
        monkeypatch.setattr(
            treino,
            'candidatos',
            lambda sku, granularidade: tuple(
                replace(c, entra=True)
                if c.algoritmo in nomes and c.espaco
                else c
                for c in tabela(sku, granularidade)
            ),
        )

    return restringir


def _diagnosticos(run_id):
    caminho = mlflow.artifacts.download_artifacts(
        run_id=run_id, artifact_path='diagnosticos.json'
    )
    return json.loads(Path(caminho).read_text(encoding='utf-8'))['ajustes']


def _prever(run):
    modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')
    return modelo.predict(pd.DataFrame({'horizonte': [HORIZONTE]}))


def test_semanal_treina_todos_os_candidatos_e_os_modelos_carregam(cfg):
    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    assert len(resumo.runs) + len(resumo.falhas) == RUNS_SEMANAIS
    assert not resumo.falhas
    assert {r.algoritmo for r in resumo.runs} == {
        'naive',
        'media_historica',
        'ets_ses',
    }
    for run in resumo.runs:
        previsao = _prever(run)
        assert len(previsao) == HORIZONTE
        assert (previsao >= 0).all()
    versoes = MlflowClient().search_model_versions(
        "name = 'demanda-item-d-semanal'"
    )
    assert len(versoes) == RUNS_SEMANAIS


def test_hiperparametros_viram_parametro_e_nome_do_run(cfg, so_estes):
    so_estes('arima', 'ets_holt_amortecido')

    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    arima = next(r for r in resumo.runs if r.algoritmo == 'arima')
    run = mlflow.get_run(arima.run_id)
    assert run.data.params['hp.ordem'] == str(arima.hiperparametros['ordem'])
    assert run.info.run_name.startswith('arima-{"ordem": [')
    holt = next(r for r in resumo.runs if r.algoritmo != 'arima')
    assert (
        mlflow.get_run(holt.run_id).data.params['hp.phi']
        == 'estimado em [0,8; 0,98]'
    )


def test_premissas_por_fold_vao_para_o_mlflow(cfg, so_estes):
    so_estes('arima')

    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    run = resumo.runs[0]
    ajustes = _diagnosticos(run.run_id)
    tags = mlflow.get_run(run.run_id).data.tags
    n_folds = len(ajustes) - 1
    assert [a['ajuste'] for a in ajustes] == [
        *(f'fold_{i}' for i in range(1, n_folds + 1)),
        'modelo_final',
    ]
    assert all(a['convergiu'] for a in ajustes)
    primeiro = {p['premissa']: p for p in ajustes[0]['premissas']}
    assert primeiro['estacionariedade']['situacao'] == NAO_TESTAVEL
    assert 'estacionariedade' in tags['premissas_nao_testaveis']


def test_baselines_nao_ganham_diagnostico(cfg, so_estes):
    so_estes('naive')

    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    tags = mlflow.get_run(resumo.runs[0].run_id).data.tags
    assert 'premissas_nao_atendidas' not in tags


def test_prophet_e_sarima_entram_na_diaria_e_servem_o_modelo(cfg, so_estes):
    so_estes('prophet', 'sarima')

    resumo = treinar_serie(cfg, 'item D', 'diaria', seed=7)

    assert not resumo.falhas
    assert {r.algoritmo for r in resumo.runs} == {'prophet', 'sarima'}
    for run in resumo.runs:
        previsao = _prever(run)
        assert len(previsao) == HORIZONTE
        assert (previsao >= 0).all()


def test_mesma_seed_reproduz_os_candidatos(cfg, so_estes):
    so_estes('prophet', 'ets_ses')

    primeira = treinar_serie(cfg, 'item D', 'diaria', seed=9)
    segunda = treinar_serie(cfg, 'item D', 'diaria', seed=9)

    assert [r.medias for r in primeira.runs] == [
        r.medias for r in segunda.runs
    ]


def test_requisitos_declaram_as_dependencias_do_previsor():
    numpy = f'numpy=={metadata.version("numpy")}'
    statsmodels = f'statsmodels=={metadata.version("statsmodels")}'
    prophet = f'prophet=={metadata.version("prophet")}'

    baseline = algoritmos.criar('naive', {}, 1)
    arima = algoritmos.criar('arima', {'ordem': (1, 0, 0)}, 1)
    modelo_prophet = algoritmos.criar('prophet', PROPHET, 1)

    assert requisitos_pip(baseline) == [numpy]
    assert statsmodels in requisitos_pip(arima)
    assert prophet in requisitos_pip(modelo_prophet)


def test_requisitos_chegam_ao_artefato(cfg, so_estes):
    so_estes('prophet')

    resumo = treinar_serie(cfg, 'item D', 'diaria', seed=7)

    caminho = mlflow.artifacts.download_artifacts(
        run_id=resumo.runs[0].run_id, artifact_path='modelo/requirements.txt'
    )
    texto = Path(caminho).read_text(encoding='utf-8')
    assert f'prophet=={metadata.version("prophet")}' in texto


class _FalhaEm:
    """Previsor que falha ao receber um treino de tamanho escolhido."""

    n_que_falha: int

    def __init__(self, alfa):
        self.alfa = alfa

    def ajustar(self, y):
        publicar_diagnostico(DiagnosticoAjuste('ets_ses', len(y), True))
        if len(y) == self.n_que_falha:
            raise FalhaConvergencia('ets_ses', {}, len(y), 'sem ótimo')
        self._ultimo = y[-1]
        return self

    def prever(self, horizonte):
        return [self._ultimo] * horizonte


@pytest.fixture
def falha_em(monkeypatch, so_estes):
    def plugar(n):
        so_estes('naive')
        classe = type('Falha', (_FalhaEm,), {'n_que_falha': n})
        algoritmos.ALGORITMOS['ets_ses'] = classe

    return plugar


def test_falha_em_um_fold_registra_run_e_nao_derruba_os_outros(cfg, falha_em):
    falha_em(7)  # treino do fold 2 da semanal

    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    assert [r.algoritmo for r in resumo.runs] == ['naive']
    [falha] = resumo.falhas
    assert falha.algoritmo == 'ets_ses'
    assert falha.ajuste == 'fold_2'
    assert falha.motivo == 'sem ótimo'
    run = mlflow.get_run(falha.run_id)
    assert run.info.status == 'FAILED'
    assert run.data.tags['falha_convergencia'] == 'true'
    assert run.data.tags['falha_ajuste'] == 'fold_2'
    assert run.data.tags['falha_motivo'] == 'sem ótimo'
    assert run.data.tags['algoritmo'] == 'ets_ses'
    assert run.data.params['hp.alfa'] == 'estimado'
    assert run.data.params['seed'] == '7'
    assert not run.data.metrics
    assert [a['ajuste'] for a in _diagnosticos(falha.run_id)] == [
        'fold_1',
        'fold_2',
    ]


def test_run_falho_nao_gera_versao_de_modelo(cfg, falha_em):
    falha_em(7)

    treinar_serie(cfg, 'item D', 'semanal', seed=7)

    versoes = MlflowClient().search_model_versions(
        "name = 'demanda-item-d-semanal'"
    )
    assert {v.tags['algoritmo'] for v in versoes} == {'naive'}


def test_falha_no_modelo_final_tambem_e_registrada(cfg, falha_em):
    falha_em(len(_particao(cfg, 'item D', 'semanal').folds) + 6)

    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    assert [f.ajuste for f in resumo.falhas] == ['modelo_final']


def test_serie_constante_registra_falhas_reais_sem_derrubar_o_treino(cfg):
    resumo = treinar_serie(cfg, 'item A', 'semanal', seed=7)

    assert resumo.falhas
    assert {r.algoritmo for r in resumo.runs} >= {'naive', 'media_historica'}
    for falha in resumo.falhas:
        assert mlflow.get_run(falha.run_id).info.status == 'FAILED'


def test_serie_sazonal_gera_diagnostico_de_sazonalidade(cfg, so_estes):
    so_estes('ets_holt_winters_aditivo')

    resumo = treinar_serie(cfg, 'item D', 'diaria', seed=7)

    ajustes = _diagnosticos(resumo.runs[0].run_id)
    premissas = {p['premissa'] for p in ajustes[0]['premissas']}
    assert 'sazonalidade' in premissas


def test_intermitentes_treinam_na_diaria_com_as_tres_combinacoes(
    cfg, so_estes
):
    so_estes('naive', *INTERMITENTES)

    resumo = treinar_serie(cfg, 'item B', 'diaria', seed=7)
    runs = [r for r in resumo.runs if r.algoritmo in INTERMITENTES]
    serie = carregar_serie(cfg, 'item B', 'diaria').to_numpy()

    treinados = {(r.algoritmo, *r.hiperparametros.values()) for r in runs}

    assert len(runs) == len(INTERMITENTES) * 3
    assert treinados == {
        (nome, alfa) for nome in INTERMITENTES for alfa in (0.1, 0.2, 0.3)
    }
    for r in runs:
        run = mlflow.get_run(r.run_id)
        chave = next(iter(r.hiperparametros))
        assert run.data.tags['algoritmo'] == r.algoritmo
        assert run.data.tags['papel'] == 'candidato'
        assert run.data.params[f'hp.{chave}'] == str(r.hiperparametros[chave])
        assert 'mae' in run.data.metrics
        modelo = mlflow.pyfunc.load_model(f'runs:/{r.run_id}/modelo')
        previsao = modelo.predict(pd.DataFrame({'horizonte': [HORIZONTE]}))
        esperado = algoritmos.criar(r.algoritmo, r.hiperparametros, 7)
        assert list(previsao) == list(
            esperado.ajustar(serie).prever(HORIZONTE)
        )


def test_intermitentes_ficam_fora_da_semanal(cfg, so_estes):
    so_estes('naive', *INTERMITENTES)

    resumo = treinar_serie(cfg, 'item B', 'semanal', seed=7)

    assert set(_por_algoritmo(resumo)).isdisjoint(INTERMITENTES)
    assert set(resumo.sem_implementacao).isdisjoint(INTERMITENTES)
