from itertools import product

import pytest

from case_mr_health.candidatos import (
    ARITMETICA,
    DECISAO_USUARIO,
    EVIDENCIA,
    HIPOTESE,
    MAX_COMBINACOES,
    SKUS,
    candidatos,
    tabela,
)

SERIES = list(product(SKUS, ('diaria', 'semanal')))
COMBINACOES_SARIMA = 3
INTERMITENTES = {'croston', 'sba', 'tsb'}
SAZONAL_CONFIRMADA = {'item B', 'item C'}


def _por_nome(sku, granularidade):
    return {c.algoritmo: c for c in candidatos(sku, granularidade)}


@pytest.mark.parametrize(('sku', 'granularidade'), SERIES)
def test_baselines_obrigatorios_entram_em_toda_serie(sku, granularidade):
    por_nome = _por_nome(sku, granularidade)

    assert por_nome['naive'].entra
    assert por_nome['media_historica'].entra
    assert por_nome['naive'].papel == 'baseline'


@pytest.mark.parametrize(('sku', 'granularidade'), SERIES)
def test_espaco_enxuto_e_toda_exclusao_tem_motivo(sku, granularidade):
    for c in candidatos(sku, granularidade):
        assert c.n_combinacoes <= MAX_COMBINACOES
        assert len(c.combinacoes()) == c.n_combinacoes
        assert c.motivo
        if not c.entra:
            assert c.combinacoes() == []
            assert c.base in {ARITMETICA, DECISAO_USUARIO, EVIDENCIA}


@pytest.mark.parametrize('sku', SKUS)
def test_naive_sazonal_diaria_separa_evidencia_de_hipotese(sku):
    c = _por_nome(sku, 'diaria')['naive_sazonal']

    assert c.entra
    assert c.espaco == {'periodo': (7,)}
    esperado = EVIDENCIA if sku in SAZONAL_CONFIRMADA else HIPOTESE
    assert c.base == esperado


@pytest.mark.parametrize('sku', SKUS)
def test_semanal_nao_tem_naive_sazonal_nem_sarima(sku):
    por_nome = _por_nome(sku, 'semanal')

    assert not por_nome['naive_sazonal'].entra
    assert not por_nome['sarima'].entra
    assert por_nome['naive_sazonal'].base == ARITMETICA
    assert por_nome['sarima'].base == ARITMETICA


@pytest.mark.parametrize('sku', SKUS)
def test_intermitentes_so_na_diaria(sku):
    diaria = _por_nome(sku, 'diaria')
    semanal = _por_nome(sku, 'semanal')

    for nome in INTERMITENTES:
        assert diaria[nome].entra
        assert diaria[nome].base == EVIDENCIA
        assert not semanal[nome].entra
    assert diaria['croston'].espaco == {'alfa': (0.1, 0.2, 0.3)}
    assert diaria['tsb'].espaco == {'alfa_beta': (0.1, 0.2, 0.3)}


@pytest.mark.parametrize('sku', SKUS)
def test_prophet_so_na_diaria_por_decisao_do_usuario_na_semanal(sku):
    assert _por_nome(sku, 'diaria')['prophet'].entra
    semanal = _por_nome(sku, 'semanal')['prophet']

    assert not semanal.entra
    assert semanal.base == DECISAO_USUARIO


@pytest.mark.parametrize('sku', SKUS)
def test_arima_semanal_entra_por_decisao_do_usuario(sku):
    c = _por_nome(sku, 'semanal')['arima']

    assert c.entra
    assert c.base == DECISAO_USUARIO
    assert c.espaco == {'ordem': ((1, 0, 0), (0, 1, 1))}
    assert 'não são testáveis' in c.motivo


@pytest.mark.parametrize('sku', SKUS)
def test_ets_diaria_sem_multiplicativo_nem_tendencia(sku):
    por_nome = _por_nome(sku, 'diaria')

    assert 'ets_holt_amortecido' not in por_nome
    hw = por_nome['ets_holt_winters_aditivo']
    assert hw.espaco == {'periodo': (7,), 'tendencia': ('nenhuma',)}


def test_sarima_diaria_usa_so_o_sazonal_ar1():
    c = _por_nome('item B', 'diaria')['sarima']

    assert c.espaco['ordem_sazonal'] == ((1, 0, 0, 7),)
    assert c.n_combinacoes == COMBINACOES_SARIMA


def test_prophet_tem_4_combinacoes_e_so_sazonalidade_semanal():
    c = _por_nome('item A', 'diaria')['prophet']

    assert c.n_combinacoes == MAX_COMBINACOES
    assert set(c.combinacoes()[0]) == {'ordem_fourier', 'escala_sazonalidade'}


def test_tabela_cobre_as_8_series_em_linhas_planas():
    linhas = tabela()

    assert {(r['sku'], r['granularidade']) for r in linhas} == set(SERIES)
    assert all(
        {'algoritmo', 'entra', 'base', 'motivo', 'espaco'} <= r.keys()
        for r in linhas
    )
    assert all(r['n_combinacoes'] <= MAX_COMBINACOES for r in linhas)


@pytest.mark.parametrize(
    ('sku', 'granularidade'), [('item Z', 'diaria'), ('item A', 'mensal')]
)
def test_serie_desconhecida_e_rejeitada(sku, granularidade):
    with pytest.raises(ValueError, match='desconhecid'):
        candidatos(sku, granularidade)
