import math

import duckdb
import mlflow
import numpy as np
import pytest
from mlflow import MlflowClient
from pydantic import ValidationError

from case_mr_health import confianca
from case_mr_health.confianca import (
    INSUFICIENTE,
    MOTIVO_FAIXA,
    MOTIVO_INDEFINIDO,
    MOTIVO_INSTAVEL,
    MOTIVO_POUCOS_FOLDS,
    avaliar,
    faixa,
    intervalo,
)
from case_mr_health.config import Settings
from case_mr_health.treino import nome_modelo, treinar_serie
from tests.test_treino import PADROES, _gravar_origem, _intermitente

LIMITES = (0.50, 0.75, 1.00)
NAN = float('nan')
SEED = 20261030
FOLDS = 5
# Dias do teste do fold 2 na série sintética de 91 dias.
TESTE_FOLD_2 = range(49, 56)
COBERTURA_NOMINAL = 0.80
TOLERANCIA_COBERTURA = 0.02


def _acima(x):
    return float(np.nextafter(x, math.inf))


@pytest.fixture
def cfg_padrao() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def cfg(tmp_path) -> Settings:
    cfg = Settings(
        _env_file=None,
        db_path=tmp_path / 'origem.duckdb',
        desenvolvimento_db_path=tmp_path / 'dev.duckdb',
        oot_db_path=tmp_path / 'fora.duckdb',
        mlflow_tracking_uri=f'sqlite:///{tmp_path / "mlflow.db"}',
        mlflow_artifact_dir=tmp_path / 'artefatos',
    )
    _gravar_origem(cfg, PADROES)
    return cfg


def _ao_redor(rng, media, dp, n=FOLDS):
    """Amostra com média e desvio-padrão amostral exatamente pedidos."""
    z = rng.standard_normal(n)
    return media + dp * (z - z.mean()) / z.std(ddof=1)


@pytest.mark.parametrize(
    ('mase', 'esperada'),
    [
        (0.0, 'Ótima'),
        (0.50, 'Ótima'),
        (_acima(0.50), 'Boa'),
        (0.75, 'Boa'),
        (_acima(0.75), 'Média'),
        (1.00, 'Média'),
        (_acima(1.00), 'Ruim'),
        (7.0, 'Ruim'),
    ],
)
def test_limite_superior_de_cada_faixa_e_inclusivo(mase, esperada):
    assert faixa(mase, LIMITES) == esperada


@pytest.mark.parametrize(
    ('mase', 'esperada'),
    [(0.5, 'Boa'), (0.51, 'Média'), (1.0, 'Média'), (1.01, 'Ruim')],
)
def test_faixas_vem_da_configuracao(mase, esperada):
    cfg = Settings(
        _env_file=None,
        confianca_limites=(0.25, 0.50, 1.00),
        confianca_max_fronteiras_ic=3,
    )

    assert avaliar([mase] * 4, cfg).status == esperada


def test_limites_sao_lidos_do_ambiente(monkeypatch):
    monkeypatch.setenv('CASE_MR_HEALTH_CONFIANCA_LIMITES', '[0.4, 0.6, 0.9]')

    assert Settings(_env_file=None).confianca_limites == (0.4, 0.6, 0.9)


@pytest.mark.parametrize(
    'limites', [(0.75, 0.50, 1.00), (0.5, 0.5, 1.0), (0.0, 0.5, 1.0)]
)
def test_limites_invalidos_sao_rejeitados(limites):
    with pytest.raises(ValidationError, match='crescente'):
        Settings(_env_file=None, confianca_limites=limites)


@pytest.mark.parametrize(
    ('mases', 'indefinidos'),
    [
        ([NAN, NAN, NAN, NAN], (1, 2, 3, 4)),
        ([NAN, 0.6, 0.7, 0.6], (1,)),
        ([0.6, 0.7, 0.6, math.inf], (4,)),
    ],
)
def test_mase_indefinido_em_algum_fold_e_insuficiente(
    mases, indefinidos, cfg_padrao
):
    resultado = avaliar(mases, cfg_padrao)

    assert resultado.status == INSUFICIENTE
    assert resultado.motivo == MOTIVO_INDEFINIDO
    assert resultado.folds_indefinidos == indefinidos
    assert resultado.faixa_pontual is None
    assert resultado.tags()['confianca_folds_indefinidos'] == ','.join(
        str(i) for i in indefinidos
    )
    assert 'confianca_mase' not in resultado.tags()


def test_erro_grande_e_estavel_e_ruim_e_nao_insuficiente(cfg_padrao):
    resultado = avaliar([5.0, 5.1, 4.9, 5.0], cfg_padrao)

    assert resultado.status == 'Ruim'
    assert resultado.motivo == MOTIVO_FAIXA


@pytest.mark.parametrize('mases', [[], [0.6]])
def test_menos_de_dois_folds_e_insuficiente(mases, cfg_padrao):
    resultado = avaliar(mases, cfg_padrao)

    assert resultado.status == INSUFICIENTE
    assert resultado.motivo == MOTIVO_POUCOS_FOLDS


def test_intervalo_confere_com_o_calculo_a_mao():
    # média 0,9; dp 0,2582; ep 0,1291; t(0,90; 3) = 1,6377
    media, dp, inferior, superior = intervalo([0.6, 0.8, 1.0, 1.2], 0.80)

    assert media == pytest.approx(0.9)
    assert dp == pytest.approx(0.2582, abs=1e-4)
    assert inferior == pytest.approx(0.6886, abs=1e-4)
    assert superior == pytest.approx(1.1114, abs=1e-4)


def test_intervalo_trunca_o_limite_inferior_em_zero():
    _, _, inferior, _ = intervalo([0.0, 0.0, 0.0, 2.0], 0.80)

    assert inferior == 0


def test_ic_que_atravessa_duas_fronteiras_e_instavel(cfg_padrao):
    # [0,6886; 1,1114] atravessa 0,75 e 1,00: Boa, Média e Ruim são possíveis.
    resultado = avaliar([0.6, 0.8, 1.0, 1.2], cfg_padrao)

    assert resultado.status == INSUFICIENTE
    assert resultado.motivo == MOTIVO_INSTAVEL
    assert resultado.faixa_pontual == 'Média'
    assert resultado.mase == pytest.approx(0.9)


def test_ic_que_atravessa_uma_fronteira_mantem_a_faixa(cfg_padrao):
    # média 0,8; ep 0,05: IC [0,718; 0,882] atravessa só 0,75.
    resultado = avaliar([0.7, 0.75, 0.85, 0.9], cfg_padrao)

    assert resultado.status == 'Média'
    assert resultado.motivo == MOTIVO_FAIXA


def test_dispersao_grande_longe_das_fronteiras_continua_ruim(cfg_padrao):
    rng = np.random.default_rng(SEED)

    resultado = avaliar(_ao_redor(rng, 4.0, 1.0), cfg_padrao)

    assert resultado.ic_inferior > 1
    assert resultado.status == 'Ruim'


def test_regra_de_instabilidade_pode_ser_desligada():
    cfg = Settings(_env_file=None, confianca_max_fronteiras_ic=3)

    assert avaliar([0.1, 0.8, 1.0, 2.0], cfg).motivo == MOTIVO_FAIXA


def test_nivel_maior_torna_o_criterio_mais_exigente():
    mases = [0.65, 0.75, 0.85, 0.95]
    cfg_80 = Settings(_env_file=None, confianca_nivel_ic=0.80)
    cfg_95 = Settings(_env_file=None, confianca_nivel_ic=0.95)

    assert avaliar(mases, cfg_80).motivo == MOTIVO_FAIXA
    assert avaliar(mases, cfg_95).motivo == MOTIVO_INSTAVEL


def test_status_nao_depende_da_ordem_dos_folds(cfg_padrao):
    rng = np.random.default_rng(SEED)
    mases = _ao_redor(rng, 0.9, 0.3)

    assert avaliar(mases, cfg_padrao) == avaliar(mases[::-1], cfg_padrao)


def test_ic_cobre_a_media_na_taxa_nominal_com_dados_independentes():
    rng = np.random.default_rng(SEED)
    media = 1.0
    amostras = rng.normal(media, 0.3, size=(20_000, FOLDS))

    cobertos = 0
    for amostra in amostras:
        _, _, inferior, superior = intervalo(amostra, COBERTURA_NOMINAL)
        cobertos += inferior <= media <= superior

    assert cobertos / len(amostras) == pytest.approx(
        COBERTURA_NOMINAL, abs=TOLERANCIA_COBERTURA
    )


def test_tags_sao_textos_e_omitem_o_indefinido(cfg_padrao):
    tags = avaliar([NAN, 0.5], cfg_padrao).tags()

    assert set(tags) == {
        'confianca',
        'confianca_motivo',
        'confianca_n_folds',
        'confianca_folds_indefinidos',
    }
    assert all(isinstance(v, str) for v in tags.values())


def _versao(run, sku, granularidade):
    return MlflowClient().get_model_version(
        nome_modelo(sku, granularidade), run.versao_modelo
    )


def _por_algoritmo(resumo):
    return {r.algoritmo: r for r in resumo.runs}


@pytest.mark.lento
def test_confianca_vai_para_a_versao_do_modelo_e_para_o_run(cfg):
    resumo = treinar_serie(cfg, 'item C', 'diaria', seed=SEED)

    run = _por_algoritmo(resumo)['naive_sazonal']
    tags = _versao(run, 'item C', 'diaria').tags

    assert tags['confianca'] == 'Ótima'  # naive sazonal exato: MASE 0
    assert tags['confianca_motivo'] == MOTIVO_FAIXA
    assert float(tags['confianca_mase']) == 0
    assert tags['confianca_n_folds'] == str(FOLDS)
    registrado = mlflow.get_run(run.run_id).data.tags
    assert registrado['confianca'] == tags['confianca']


@pytest.mark.lento
def test_todas_as_versoes_recebem_confianca(cfg):
    resumo = treinar_serie(cfg, 'item B', 'semanal', seed=SEED)

    for run in resumo.runs:
        tags = _versao(run, 'item B', 'semanal').tags
        assert tags['confianca'] in {*confianca.FAIXAS, INSUFICIENTE}


@pytest.mark.lento
def test_escala_zero_vira_insuficiente_coerente_com_a_tag_do_run(cfg):
    resumo = treinar_serie(cfg, 'item A', 'diaria', seed=SEED)

    run = _por_algoritmo(resumo)['naive']
    tags = _versao(run, 'item A', 'diaria').tags

    assert run.medias['mae'] == 0  # erro zero não vira Ótima sem evidência
    assert tags['confianca'] == INSUFICIENTE
    assert tags['confianca_motivo'] == MOTIVO_INDEFINIDO
    assert tags['confianca_folds_indefinidos'] == '1,2,3,4,5'
    assert 'confianca_faixa_pontual' not in tags
    indefinidas = mlflow.get_run(run.run_id).data.tags['metricas_indefinidas']
    assert 'mase' in indefinidas.split(',')


def _zera_o_teste_do_fold_2(i):
    return 0 if i in TESTE_FOLD_2 else _intermitente(i)


@pytest.mark.lento
def test_wape_indefinido_nao_torna_a_confianca_insuficiente(cfg):
    _gravar_origem(cfg, dict(PADROES, **{'item B': _zera_o_teste_do_fold_2}))

    resumo = treinar_serie(cfg, 'item B', 'diaria', seed=SEED)

    run = _por_algoritmo(resumo)['naive']
    indefinidas = mlflow.get_run(run.run_id).data.tags['metricas_indefinidas']
    tags = _versao(run, 'item B', 'diaria').tags
    assert 'wape' in indefinidas.split(',')
    assert 'mase' not in indefinidas.split(',')
    assert tags['confianca_motivo'] != MOTIVO_INDEFINIDO


@pytest.mark.lento
def test_confianca_nao_depende_do_oot(cfg):
    antes = treinar_serie(cfg, 'item C', 'diaria', seed=SEED)
    con = duckdb.connect(str(cfg.oot_db_path))
    try:
        con.execute('UPDATE serie_diaria SET quantidade = quantidade + 999')
    finally:
        con.close()

    depois = treinar_serie(cfg, 'item C', 'diaria', seed=SEED)

    for run_antes, run_depois in zip(antes.runs, depois.runs, strict=True):
        tags_antes = _versao(run_antes, 'item C', 'diaria').tags
        tags_depois = _versao(run_depois, 'item C', 'diaria').tags
        for chave in ('confianca', 'confianca_mase', 'confianca_mase_dp'):
            assert tags_antes.get(chave) == tags_depois.get(chave)


@pytest.mark.lento
def test_confianca_nao_promove_nenhuma_versao(cfg):
    treinar_serie(cfg, 'item C', 'diaria', seed=SEED)

    cliente = MlflowClient()
    for versao in cliente.search_model_versions(
        "name = 'demanda-item-c-diaria'"
    ):
        atual = cliente.get_model_version(versao.name, versao.version)
        assert not atual.aliases
