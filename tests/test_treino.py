import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow import MlflowClient

from case_mr_health import algoritmos
from case_mr_health.cli import app
from case_mr_health.config import Settings
from case_mr_health.particoes import carregar_particoes, separar_series
from case_mr_health.treino import (
    ModeloDemanda,
    carregar_serie,
    hash_artefato,
    nome_modelo,
    normalizar_sku,
    seed_padrao,
    treinar_serie,
)

INICIO = date(2021, 6, 7)  # segunda-feira
TAMANHO_SHA256 = 64
HORIZONTE = 14
TREINO_MINIMO_DIARIA = 42
SEED_DE_20210901 = 20210901
N_DIAS = 91  # 13 semanas completas: 5 folds na diária e 5 na semanal
SEED = 5
BASELINES = {'naive', 'media_historica', 'naive_sazonal'}
SEMANAS_SERVIDAS = 2


def _constante(i):
    return 5


def _intermitente(i):
    return [0, 0, 3, 0, 1, 0, 0, 2, 0, 0, 4, 0, 0, 0][i % 14]


def _sazonal(i):
    return [1, 1, 2, 2, 8, 9, 7][i % 7]  # fim de semana forte


PADROES = {
    'item A': _constante,
    'item B': _intermitente,
    'item C': _sazonal,
    'item D': _sazonal,
}


def _gravar_origem(cfg: Settings, padroes: dict) -> None:
    """Tabelas de série sintéticas (como `construir_series`) e a separação."""
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.db_path.unlink(missing_ok=True)
    con = duckdb.connect(str(cfg.db_path))
    try:
        con.execute(
            'CREATE TABLE serie_diaria (sku VARCHAR, data DATE, '
            'quantidade BIGINT, imputado BOOLEAN)'
        )
        con.execute(
            'CREATE TABLE serie_semanal (sku VARCHAR, semana DATE, '
            'quantidade BIGINT)'
        )
        for sku, padrao in padroes.items():
            valores = [padrao(i) for i in range(N_DIAS)]
            con.executemany(
                'INSERT INTO serie_diaria VALUES (?, ?, ?, ?)',
                [
                    [sku, INICIO + timedelta(days=i), v, v == 0]
                    for i, v in enumerate(valores)
                ],
            )
            con.executemany(
                'INSERT INTO serie_semanal VALUES (?, ?, ?)',
                [
                    [
                        sku,
                        INICIO + timedelta(weeks=s),
                        sum(valores[7 * s :][:7]),
                    ]
                    for s in range(N_DIAS // 7)
                ],
            )
    finally:
        con.close()
    separar_series(cfg)


@pytest.fixture(autouse=True)
def so_baselines(monkeypatch):
    """Fluxo com baselines; os demais: `test_treino_candidatos`."""
    monkeypatch.setattr(
        algoritmos,
        'ALGORITMOS',
        {n: algoritmos.ALGORITMOS[n] for n in sorted(BASELINES)},
    )


@pytest.fixture
def cfg(tmp_path) -> Settings:
    cfg = Settings(
        db_path=tmp_path / 'origem.duckdb',
        desenvolvimento_db_path=tmp_path / 'dev.duckdb',
        oot_db_path=tmp_path / 'fora.duckdb',
        mlflow_tracking_uri=f'sqlite:///{tmp_path / "mlflow.db"}',
        mlflow_artifact_dir=tmp_path / 'artefatos',
    )
    _gravar_origem(cfg, PADROES)
    return cfg


def _por_algoritmo(resumo):
    return {r.algoritmo: r for r in resumo.runs}


def _medias(resumo):
    """Médias por candidato; `nan` (MASE indefinido) vira `None`."""
    return {
        r.algoritmo: {
            k: None if math.isnan(v) else v for k, v in r.medias.items()
        }
        for r in resumo.runs
    }


def _particao(cfg, sku, granularidade):
    return next(
        p
        for p in carregar_particoes(cfg)
        if (p.sku, p.granularidade) == (sku, granularidade)
    )


def test_treina_baselines_da_diaria_e_registra_o_modelo_por_sku(cfg):
    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=7)

    assert BASELINES <= set(_por_algoritmo(resumo))
    cliente = MlflowClient()
    [modelo] = cliente.search_registered_models(
        filter_string="name = 'demanda-item-c-diaria'"
    )
    assert modelo.name == nome_modelo('item C', 'diaria')
    versoes = cliente.search_model_versions("name = 'demanda-item-c-diaria'")
    assert len(versoes) == len(resumo.runs)
    for v in versoes:
        assert len(v.tags['hash_artefato']) == TAMANHO_SHA256
        assert v.tags['algoritmo'] in _por_algoritmo(resumo)


def test_baselines_da_semanal_nao_incluem_naive_sazonal(cfg):
    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)

    assert set(_por_algoritmo(resumo)) == {'naive', 'media_historica'}


def test_hash_do_artefato_confere_com_o_modelo_baixado(cfg):
    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=7)
    run = _por_algoritmo(resumo)['naive']

    baixado = Path(
        mlflow.artifacts.download_artifacts(
            run_id=run.run_id, artifact_path='modelo'
        )
    )

    assert hash_artefato(baixado) == run.hash_artefato


def test_naive_sazonal_e_exato_na_serie_sazonal(cfg):
    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=7)

    medias = _por_algoritmo(resumo)['naive_sazonal'].medias

    assert medias['mae'] == 0
    assert medias['wape'] == 0
    assert _por_algoritmo(resumo)['naive'].medias['mae'] > 0


def test_serie_constante_tem_erro_zero_e_mase_indefinido(cfg):
    resumo = treinar_serie(cfg, 'item A', 'diaria', seed=7)
    naive = _por_algoritmo(resumo)['naive']

    run = mlflow.get_run(naive.run_id)

    assert naive.medias['mae'] == 0
    assert math.isnan(naive.medias['mase'])  # escala zero: sem evidência (#9)
    assert 'mase' in run.data.tags['metricas_indefinidas']
    assert 'mase' not in run.data.metrics


def test_modelo_registrado_preve_sem_valores_negativos(cfg):
    resumo = treinar_serie(cfg, 'item B', 'diaria', seed=7)

    for run in resumo.runs:
        modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')
        previsao = modelo.predict(pd.DataFrame({'horizonte': [HORIZONTE]}))
        assert len(previsao) == HORIZONTE
        assert (previsao >= 0).all()


def test_run_registra_tags_parametros_e_particoes(cfg):
    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=7)
    run = mlflow.get_run(_por_algoritmo(resumo)['naive_sazonal'].run_id)
    particao = _particao(cfg, 'item C', 'diaria')

    assert run.data.tags['sku'] == 'item C'
    assert run.data.tags['granularidade'] == 'diaria'
    assert run.data.tags['algoritmo'] == 'naive_sazonal'
    params = run.data.params
    assert params['seed'] == '7'
    assert params['hp.periodo'] == '7'
    assert params['n_observacoes'] == str(N_DIAS - cfg.oot_diaria_dias)
    assert params['n_folds'] == str(len(particao.folds))
    assert params['desenvolvimento_fim'] == str(particao.desenvolvimento_fim)
    assert params['oot_inicio'] == str(particao.oot_inicio)
    for i, fold in enumerate(particao.folds, start=1):
        teste = f'{fold.teste_inicio}/{fold.teste_fim}'
        assert params[f'fold_{i}.teste'] == teste
    assert params['codigo.pacote']
    assert 'codigo.commit' in params
    config = json.loads(
        Path(
            mlflow.artifacts.download_artifacts(
                run_id=run.info.run_id, artifact_path='config.json'
            )
        ).read_text(encoding='utf-8')
    )
    assert config['treino_minimo_diaria_dias'] == TREINO_MINIMO_DIARIA
    assert 'mae' in run.data.metrics
    historico = MlflowClient().get_metric_history(run.info.run_id, 'mae_fold')
    assert len(historico) == len(particao.folds)


def test_experimentos_filtraveis_por_sku_granularidade_e_algoritmo(cfg):
    treinar_serie(cfg, 'item C', 'diaria', seed=7)
    treinar_serie(cfg, 'item D', 'diaria', seed=7)
    treinar_serie(cfg, 'item C', 'semanal', seed=7)

    encontrados = mlflow.search_runs(
        experiment_names=['demanda-diaria'],
        filter_string="tags.sku = 'item C' and tags.algoritmo = 'naive'",
    )
    semanais = mlflow.search_runs(experiment_names=['demanda-semanal'])

    assert len(encontrados) == 1
    assert set(semanais['tags.granularidade']) == {'semanal'}
    assert set(semanais['tags.sku']) == {'item C'}


def test_alterar_o_oot_nao_muda_o_backtest(cfg):
    antes = treinar_serie(cfg, 'item C', 'diaria', seed=7)
    con = duckdb.connect(str(cfg.oot_db_path))
    try:
        con.execute('UPDATE serie_diaria SET quantidade = quantidade + 999')
    finally:
        con.close()

    depois = treinar_serie(cfg, 'item C', 'diaria', seed=7)

    assert _medias(antes) == _medias(depois)
    particao = _particao(cfg, 'item C', 'diaria')
    serie = carregar_serie(cfg, 'item C', 'diaria')
    assert serie.index.max().date() == particao.desenvolvimento_fim
    assert serie.index.max().date() < particao.oot_inicio


def test_mesma_seed_reproduz_metricas_e_registra_a_seed(cfg):
    primeira = treinar_serie(cfg, 'item D', 'semanal', seed=123)
    segunda = treinar_serie(cfg, 'item D', 'semanal', seed=123)

    assert _medias(primeira) == _medias(segunda)
    for r in (*primeira.runs, *segunda.runs):
        assert mlflow.get_run(r.run_id).data.params['seed'] == '123'


def test_series_sao_independentes(cfg):
    antes = treinar_serie(cfg, 'item A', 'diaria', seed=7)
    outros = dict(PADROES, **{'item B': _sazonal, 'item C': _intermitente})
    _gravar_origem(cfg, outros)

    depois = treinar_serie(cfg, 'item A', 'diaria', seed=7)

    assert _medias(antes) == _medias(depois)
    nomes = {m.name for m in MlflowClient().search_registered_models()}
    assert nomes == {'demanda-item-a-diaria'}


def test_sensibilidade_do_item_c_semanal_vai_ao_mlflow(cfg):
    item_c = treinar_serie(cfg, 'item C', 'semanal', seed=7)
    item_a = treinar_serie(cfg, 'item A', 'semanal', seed=7)

    run_c = mlflow.get_run(_por_algoritmo(item_c)['naive'].run_id)
    run_a = mlflow.get_run(_por_algoritmo(item_a)['naive'].run_id)

    assert 'sens_sem_periodo_atipico_mae' in run_c.data.metrics
    assert 'sens_sem_folds_1_2_mae' in run_c.data.metrics
    assert not any(k.startswith('sens_') for k in run_a.data.metrics)


def test_candidatos_sem_implementacao_sao_reportados(cfg):
    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=7)

    assert 'ets_ses' in resumo.sem_implementacao
    assert set(resumo.sem_implementacao).isdisjoint(algoritmos.ALGORITMOS)


def test_candidato_plugado_entra_no_fluxo_sem_mudancas(cfg, monkeypatch):
    monkeypatch.setattr(algoritmos, 'ALGORITMOS', dict(algoritmos.ALGORITMOS))

    @algoritmos.registrar('ets_ses')
    class Fixo:
        def __init__(self, alfa):
            self.alfa = alfa

        def ajustar(self, y):
            self.ultimo = y[-1]
            return self

        def prever(self, horizonte):
            return [self.ultimo] * horizonte

    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=7)

    assert 'ets_ses' in _por_algoritmo(resumo)
    assert 'ets_ses' not in resumo.sem_implementacao


def test_cobertura_do_backtest_vai_ao_mlflow(cfg):
    resumo = treinar_serie(cfg, 'item B', 'diaria', seed=7)
    particao = _particao(cfg, 'item B', 'diaria')

    for r in resumo.runs:
        run = mlflow.get_run(r.run_id)
        metricas = run.data.metrics
        for nivel in ('80', '95'):
            assert 0 <= metricas[f'cobertura_{nivel}'] <= 1
            assert (
                metricas[f'cobertura_{nivel}_ic_inf']
                <= metricas[f'cobertura_{nivel}']
                <= metricas[f'cobertura_{nivel}_ic_sup']
            )
            assert metricas[f'amplitude_{nivel}'] >= 0
            historico = MlflowClient().get_metric_history(
                r.run_id, f'cobertura_{nivel}_fold'
            )
            assert len(historico) == len(particao.folds)
        n_pontos = 7 * len(particao.folds)
        assert metricas['cobertura_n_pontos'] == n_pontos
        assert metricas['cobertura_80'] == r.cobertura[0.80]


def test_metodo_do_intervalo_fica_no_run_e_na_versao(cfg):
    resumo = treinar_serie(cfg, 'item C', 'semanal', seed=7)
    run = _por_algoritmo(resumo)['naive']

    registrado = mlflow.get_run(run.run_id)
    [versao] = MlflowClient().search_model_versions(
        f"name = 'demanda-item-c-semanal' and run_id = '{run.run_id}'"
    )

    assert registrado.data.tags['intervalo_metodo'] == 'empirico_t'
    assert registrado.data.tags['intervalo_motivo'] == 'sem_nativo'
    assert registrado.data.params['intervalo.horizonte'] == '2'
    assert registrado.data.params['fold_1.intervalo_metodo'] == 'empirico_t'
    assert versao.tags['intervalo_metodo'] == 'empirico_t'
    assert versao.tags['intervalo_horizonte'] == '2'
    assert json.loads(versao.tags['intervalo_niveis']) == [0.8, 0.95]


def test_modelo_registrado_expoe_os_limites(cfg):
    resumo = treinar_serie(cfg, 'item B', 'diaria', seed=7)

    for run in resumo.runs:
        modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')
        saida = modelo.predict(
            pd.DataFrame({'horizonte': [HORIZONTE], 'intervalos': [True]})
        )

        assert list(saida.columns) == [
            'previsao',
            'inferior_80',
            'superior_80',
            'inferior_95',
            'superior_95',
        ]
        assert len(saida) == HORIZONTE
        assert (saida >= 0).all(axis=None)
        assert (saida['inferior_95'] <= saida['inferior_80']).all()
        assert (saida['inferior_80'] <= saida['previsao']).all()
        assert (saida['previsao'] <= saida['superior_80']).all()
        assert (saida['superior_80'] <= saida['superior_95']).all()
        ponto = modelo.predict(pd.DataFrame({'horizonte': [HORIZONTE]}))
        assert saida['previsao'].tolist() == pytest.approx(list(ponto))


def test_modelo_final_aplica_o_piso_zero_com_os_zeros_do_desenvolvimento(
    cfg,
):
    # Item B intermitente: maioria de zeros em todo o desenvolvimento.
    resumo = treinar_serie(cfg, 'item B', 'diaria', seed=7)

    for run in resumo.runs:
        registrado = mlflow.get_run(run.run_id)
        assert float(registrado.data.params['intervalo.fracao_zeros']) > 0.5  # noqa: PLR2004
        modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')
        saida = modelo.predict(
            pd.DataFrame({'horizonte': [HORIZONTE], 'intervalos': [True]})
        )
        assert (saida['inferior_80'] == 0).all()
        assert (saida['inferior_95'] == 0).all()


def test_modelo_nao_extrapola_o_horizonte_calibrado(cfg):
    resumo = treinar_serie(cfg, 'item D', 'semanal', seed=7)
    run = _por_algoritmo(resumo)['naive']
    modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')

    entrada = {'horizonte': [SEMANAS_SERVIDAS + 1], 'intervalos': [True]}
    with pytest.raises(ValueError, match='acima do calibrado'):
        modelo.predict(pd.DataFrame(entrada))


def test_modelo_sem_calibracao_nao_serve_intervalos():
    modelo = ModeloDemanda(algoritmos.Naive().ajustar([1, 2]))

    with pytest.raises(ValueError, match='sem calibração'):
        modelo.prever_com_intervalos(2)


def test_niveis_vem_da_configuracao(cfg):
    outro = cfg.model_copy(update={'niveis_intervalo': (0.5, 0.9)})

    resumo = treinar_serie(outro, 'item C', 'diaria', seed=7)

    run = _por_algoritmo(resumo)['naive']
    assert 'cobertura_50' in mlflow.get_run(run.run_id).data.metrics
    modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')
    saida = modelo.predict(
        pd.DataFrame({'horizonte': [3], 'intervalos': [True]})
    )
    assert 'superior_90' in saida.columns


def test_alterar_o_oot_nao_muda_a_cobertura_nem_a_calibracao(cfg):
    antes = treinar_serie(cfg, 'item C', 'diaria', seed=7)
    con = duckdb.connect(str(cfg.oot_db_path))
    try:
        con.execute('UPDATE serie_diaria SET quantidade = quantidade + 999')
    finally:
        con.close()

    depois = treinar_serie(cfg, 'item C', 'diaria', seed=7)

    for a, b in zip(antes.runs, depois.runs, strict=True):
        assert a.cobertura == b.cobertura
        modelos = [
            mlflow.pyfunc.load_model(f'runs:/{r.run_id}/modelo')
            for r in (a, b)
        ]
        limites = [
            m.predict(pd.DataFrame({'horizonte': [7], 'intervalos': [True]}))
            for m in modelos
        ]
        assert limites[0].equals(limites[1])


def test_mesma_seed_reproduz_a_cobertura(cfg):
    primeira = treinar_serie(cfg, 'item B', 'semanal', seed=123)
    segunda = treinar_serie(cfg, 'item B', 'semanal', seed=123)

    for a, b in zip(primeira.runs, segunda.runs, strict=True):
        assert a.cobertura == b.cobertura


def test_sensibilidade_da_cobertura_do_item_c_vai_ao_mlflow(cfg):
    resumo = treinar_serie(cfg, 'item C', 'semanal', seed=7)

    run = mlflow.get_run(_por_algoritmo(resumo)['naive'].run_id)

    assert 'sens_sem_periodo_atipico_cobertura_95' in run.data.metrics


def test_previsor_com_nativo_calibrado_e_servido_pelo_nativo(cfg, monkeypatch):
    monkeypatch.setattr(algoritmos, 'ALGORITMOS', dict(algoritmos.ALGORITMOS))
    gerador = np.random.default_rng(3)
    ruido = gerador.normal(20, 3, N_DIAS).round().clip(0)
    _gravar_origem(cfg, {'item A': lambda i: int(ruido[i])})

    @algoritmos.registrar('ets_ses')
    class ComNativo:
        def __init__(self, alfa):
            self.alfa = alfa

        def ajustar(self, y):
            self.media = float(np.mean(y))
            return self

        def prever(self, horizonte):
            return np.full(horizonte, self.media)

        def intervalos_nativos(self, horizonte, niveis):
            meia = {0.80: 3.85, 0.95: 5.9}
            return {
                n: (
                    np.full(horizonte, self.media - meia[n]),
                    np.full(horizonte, self.media + meia[n]),
                )
                for n in niveis
            }

    resumo = treinar_serie(cfg, 'item A', 'diaria', seed=7)

    run = _por_algoritmo(resumo)['ets_ses']
    registrado = mlflow.get_run(run.run_id)
    assert run.intervalo_metodo == 'nativo'
    assert registrado.data.tags['intervalo_motivo'] == 'calibrado'
    assert 'cobertura_nativo_95' in registrado.data.metrics
    assert 'cobertura_empirico_95' in registrado.data.metrics
    modelo = mlflow.pyfunc.load_model(f'runs:/{run.run_id}/modelo')
    saida = modelo.predict(
        pd.DataFrame({'horizonte': [3], 'intervalos': [True]})
    )
    largura = saida['superior_95'] - saida['inferior_95']
    assert largura.tolist() == pytest.approx([11.8] * 3)


def test_seed_padrao_e_a_data_local_de_sao_paulo():
    meia_noite_utc = datetime(2021, 9, 2, 1, 0, tzinfo=ZoneInfo('UTC'))

    assert seed_padrao(Settings(seed=None), meia_noite_utc) == SEED_DE_20210901
    assert seed_padrao(Settings(seed=SEED), meia_noite_utc) == SEED


@pytest.mark.parametrize(
    ('entrada', 'esperado'), [('A', 'item A'), ('item d', 'item D')]
)
def test_normalizar_sku_aceita_a_letra(entrada, esperado):
    assert normalizar_sku(entrada) == esperado


def test_sku_e_granularidade_invalidos_sao_rejeitados(cfg):
    with pytest.raises(ValueError, match='SKU desconhecido'):
        treinar_serie(cfg, 'item Z', 'diaria')
    with pytest.raises(ValueError, match='granularidade desconhecida'):
        treinar_serie(cfg, 'item A', 'mensal')


def test_comando_treinar(cfg, monkeypatch):
    for chave, valor in {
        'DESENVOLVIMENTO_DB_PATH': cfg.desenvolvimento_db_path,
        'MLFLOW_TRACKING_URI': cfg.mlflow_tracking_uri,
        'MLFLOW_ARTIFACT_DIR': cfg.mlflow_artifact_dir,
    }.items():
        monkeypatch.setenv(f'CASE_MR_HEALTH_{chave}', str(valor))

    codigo = app(
        ['treinar', '--sku', 'C', '--granularidade', 'semanal', '--seed', '9'],
        result_action='return_value',
    )
    invalido = app(
        ['treinar', '--sku', 'Z', '--granularidade', 'semanal'],
        result_action='return_value',
    )

    assert codigo == 0
    assert invalido == 1
    runs = mlflow.search_runs(experiment_names=['demanda-semanal'])
    assert set(runs['params.seed']) == {'9'}
