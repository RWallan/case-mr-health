import warnings
from types import SimpleNamespace

import cloudpickle
import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.tools.sm_exceptions import ConvergenceWarning

from case_mr_health import algoritmos, algoritmos_statsmodels
from case_mr_health.algoritmos import criar
from case_mr_health.algoritmos_statsmodels import (
    FalhaConvergencia,
    ajustar_monitorado,
    coletar_diagnosticos,
    verificar_dependencia,
    verificar_estacionariedade,
    verificar_parametros,
    verificar_raizes,
    verificar_residuos,
    verificar_sazonalidade,
    verificar_zeros,
)
from case_mr_health.backtest import rodar_backtest
from case_mr_health.candidatos import (
    ATENDIDA,
    INCONCLUSIVA,
    NAO_ATENDIDA,
    NAO_TESTAVEL,
    SKUS,
    candidatos,
)
from case_mr_health.config import Settings
from case_mr_health.particoes import GRANULARIDADES, particionar

FAMILIAS = {'ets', 'arima', 'prophet'}
INICIO_SERIE = '2021-06-07'
PADRAO_SEMANAL = (1, 1, 2, 2, 8, 9, 7)
NIVEIS = (0.80, 0.95)
LIMITES_PHI = (0.8, 0.98)
LAG_MAXIMO_EM_42 = 8  # 42 / 5
N_FALHA = 9
N_SAZONAL = 84
N_CURTO_SEMANAL = 6
HORIZONTE = 5


def _sazonal(seed: int, n: int = N_SAZONAL, ruido: float = 0.7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    ciclo = np.resize(PADRAO_SEMANAL, n)
    return ciclo * 3.0 + 10 + rng.normal(0, ruido, n)


def _ruido(seed: int, n: int = 60) -> np.ndarray:
    return 20 + np.random.default_rng(seed).normal(0, 3, n)


def _ar1(seed: int, n: int = 80, phi: float = 0.6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = phi * y[t - 1] + rng.normal()
    return y + 30


def _situacao(diagnostico, premissa):
    return next(
        p.situacao for p in diagnostico.premissas if p.premissa == premissa
    )


def _combinacoes_da_tabela():
    return sorted({
        (c.algoritmo, repr(hp))
        for sku in SKUS
        for gran in GRANULARIDADES
        for c in candidatos(sku, gran)
        if c.familia in FAMILIAS
        for hp in c.combinacoes()
    })


@pytest.mark.parametrize(('algoritmo', 'hp'), _combinacoes_da_tabela())
def test_toda_combinacao_da_tabela_tem_implementacao(algoritmo, hp):
    hiperparametros = eval(hp)  # noqa: S307 (repr de `candidatos.py`)

    previsor = criar(algoritmo, hiperparametros, seed=1)

    assert algoritmo in algoritmos.ALGORITMOS
    assert hasattr(previsor, 'intervalos_nativos')


@pytest.mark.parametrize(
    ('algoritmo', 'hiperparametros', 'mensagem'),
    [
        ('ets_ses', {'alfa': 0.3}, 'alfa sem mapeamento'),
        (
            'ets_holt_winters_aditivo',
            {'periodo': 7, 'tendencia': 'aditiva'},
            'tendência sem mapeamento',
        ),
        ('ets_holt_amortecido', {'phi': 0.9}, 'phi sem mapeamento'),
    ],
)
def test_valor_simbolico_desconhecido_e_rejeitado(
    algoritmo, hiperparametros, mensagem
):
    with pytest.raises(ValueError, match=mensagem):
        criar(algoritmo, hiperparametros, seed=1)


def test_ordem_aceita_a_lista_que_volta_do_json():
    pela_tupla = criar('arima', {'ordem': (1, 0, 0)}, 1).ajustar(_ar1(1))
    pela_lista = criar('arima', {'ordem': [1, 0, 0]}, 1).ajustar(_ar1(1))

    assert pela_lista.ordem == (1, 0, 0)
    assert np.array_equal(pela_tupla.prever(3), pela_lista.prever(3))


@pytest.mark.parametrize(
    ('ordem', 'com_constante'),
    [((1, 0, 0), True), ((0, 0, 1), True), ((0, 1, 1), False)],
)
def test_constante_segue_a_tabela(ordem, com_constante):
    previsor = criar('arima', {'ordem': ordem}, 1).ajustar(_ar1(2))

    assert ('const' in previsor._resultado.param_names) is com_constante


def test_sarima_tem_constante_e_termo_sazonal():
    previsor = criar(
        'sarima',
        {'ordem': (0, 0, 0), 'ordem_sazonal': (1, 0, 0, 7)},
        1,
    ).ajustar(_sazonal(1))

    assert previsor._resultado.param_names == ['const', 'ar.S.L7', 'sigma2']


def test_ar1_confere_com_a_recursao_a_mao():
    y = _ar1(3)
    previsor = criar('arima', {'ordem': (1, 0, 0)}, 1).ajustar(y)
    media, phi, _ = previsor._resultado.params

    esperado = media + phi ** np.arange(1, 5) * (y[-1] - media)

    assert np.allclose(previsor.prever(4), esperado)


def test_sarima_sazonal_puro_confere_com_a_recursao_a_mao():
    y = _sazonal(4)
    previsor = criar(
        'sarima',
        {'ordem': (0, 0, 0), 'ordem_sazonal': (1, 0, 0, 7)},
        1,
    ).ajustar(y)
    media, phi, _ = previsor._resultado.params

    esperado = media + phi * (y[-7:] - media)

    assert np.allclose(previsor.prever(7), esperado)


def test_arima_011_preve_um_nivel_constante():
    previsor = criar('arima', {'ordem': (0, 1, 1)}, 1).ajustar(_ruido(1))

    assert np.allclose(previsor.prever(4), previsor.prever(1)[0])


def test_ses_confere_com_a_recursao_a_mao():
    y = _ruido(5)
    previsor = criar('ets_ses', {'alfa': 'estimado'}, 1).ajustar(y)
    alfa, nivel = previsor._resultado.params

    for valor in y:
        nivel += alfa * (valor - nivel)

    assert np.allclose(previsor.prever(3), nivel)


def test_holt_amortecido_confere_com_a_recursao_a_mao():
    y = np.cumsum(np.random.default_rng(6).normal(1, 1, 30)) + 50
    previsor = criar(
        'ets_holt_amortecido', {'phi': 'estimado em [0,8; 0,98]'}, 1
    ).ajustar(y)
    resultado = previsor._resultado
    phi = resultado.params[resultado.param_names.index('damping_trend')]
    nivel = resultado.level.iloc[-1]
    inclinacao = resultado.slope.iloc[-1]

    esperado = nivel + inclinacao * np.cumsum(phi ** np.arange(1, 5))

    assert LIMITES_PHI[0] <= phi <= LIMITES_PHI[1]
    assert np.allclose(previsor.prever(4), esperado)


def test_holt_winters_nao_tem_tendencia_e_repete_o_ciclo():
    previsor = criar(
        'ets_holt_winters_aditivo',
        {'periodo': 7, 'tendencia': 'nenhuma'},
        1,
    ).ajustar(_sazonal(7))

    previsao = previsor.prever(14)

    assert 'smoothing_trend' not in previsor._resultado.param_names
    assert np.allclose(previsao[:7], previsao[7:])


@pytest.mark.parametrize(
    ('algoritmo', 'hiperparametros', 'y'),
    [
        ('ets_ses', {'alfa': 'estimado'}, _ruido(8)),
        (
            'ets_holt_winters_aditivo',
            {'periodo': 7, 'tendencia': 'nenhuma'},
            _sazonal(8),
        ),
        (
            'ets_holt_amortecido',
            {'phi': 'estimado em [0,8; 0,98]'},
            _ruido(9),
        ),
        ('arima', {'ordem': (1, 0, 1)}, _ar1(8)),
        (
            'sarima',
            {'ordem': (1, 0, 0), 'ordem_sazonal': (1, 0, 0, 7)},
            _sazonal(9),
        ),
    ],
)
def test_intervalos_nativos_e_serializacao(algoritmo, hiperparametros, y):
    previsor = criar(algoritmo, hiperparametros, 1).ajustar(y)
    previsao = previsor.prever(HORIZONTE)

    intervalos = previsor.intervalos_nativos(HORIZONTE, NIVEIS)
    carregado = cloudpickle.loads(cloudpickle.dumps(previsor))

    assert set(intervalos) == set(NIVEIS)
    baixo_80, alto_80 = intervalos[0.80]
    baixo_95, alto_95 = intervalos[0.95]
    assert len(baixo_80) == len(alto_80) == HORIZONTE
    assert (baixo_95 < baixo_80).all()
    assert (baixo_80 < previsao).all()
    assert (previsao < alto_80).all()
    assert (alto_80 < alto_95).all()
    assert np.array_equal(carregado.prever(HORIZONTE), previsao)
    assert np.array_equal(
        carregado.intervalos_nativos(HORIZONTE, NIVEIS)[0.95][1], alto_95
    )


def test_intervalo_do_ses_confere_com_a_formula_a_mao():
    previsor = criar('ets_ses', {'alfa': 'estimado'}, 1).ajustar(_ruido(10))
    resultado = previsor._resultado
    alfa = resultado.params[0]
    passos = np.arange(1, 4)

    baixo, alto = previsor.intervalos_nativos(3, (0.95,))[0.95]

    variancia = resultado.mse * (1 + (passos - 1) * alfa**2)
    meia_largura = stats.norm.ppf(0.975) * np.sqrt(variancia)
    assert np.allclose(alto - previsor.prever(3), meia_largura)
    assert np.allclose(previsor.prever(3) - baixo, meia_largura)


def test_intervalos_nao_sao_truncados_em_zero():
    y = np.random.default_rng(11).normal(0.5, 2, 60)

    previsor = criar('arima', {'ordem': (1, 0, 0)}, 1).ajustar(y)

    assert previsor.intervalos_nativos(3, (0.95,))[0.95][0].min() < 0


@pytest.mark.parametrize('seed', [20261030, 11, 12, 13, 14])
@pytest.mark.parametrize(
    ('algoritmo', 'hiperparametros'),
    [
        (
            'sarima',
            {'ordem': (0, 0, 0), 'ordem_sazonal': (1, 0, 0, 7)},
        ),
        ('ets_holt_winters_aditivo', {'periodo': 7, 'tendencia': 'nenhuma'}),
    ],
)
def test_sazonal_supera_o_naive_na_serie_sazonal(
    algoritmo, hiperparametros, seed
):
    y = _sazonal(seed)
    datas = pd.date_range(INICIO_SERIE, periods=len(y), freq='D')
    serie = pd.Series(y, index=datas)
    particao = particionar(
        'item C', 'diaria', [d.date() for d in datas], Settings()
    )
    desenvolvimento = serie[serie.index.date <= particao.desenvolvimento_fim]

    sazonal = rodar_backtest(
        desenvolvimento, particao, algoritmo, hiperparametros, seed
    )
    naive = rodar_backtest(desenvolvimento, particao, 'naive', {}, seed)

    assert sazonal.medias['mae'] < naive.medias['mae']
    for fold in sazonal.folds:
        assert min(fold.previsto) >= 0


def test_previsao_negativa_e_truncada_no_backtest():
    y = np.abs(np.random.default_rng(12).normal(0, 1, N_SAZONAL)) * (
        np.arange(N_SAZONAL)[::-1] / N_SAZONAL
    )
    datas = pd.date_range(INICIO_SERIE, periods=len(y), freq='D')
    particao = particionar(
        'item C', 'diaria', [d.date() for d in datas], Settings()
    )
    serie = pd.Series(y, index=datas)[: -Settings().oot_diaria_dias]

    resultado = rodar_backtest(
        serie,
        particao,
        'ets_holt_winters_aditivo',
        {'periodo': 7, 'tendencia': 'nenhuma'},
        1,
    )

    assert all(min(f.previsto) >= 0 for f in resultado.folds)


def test_semanal_com_seis_pontos_relata_o_que_nao_e_testavel():
    y = _ruido(13, n=N_CURTO_SEMANAL)

    with coletar_diagnosticos() as coletados:
        criar('arima', {'ordem': (1, 0, 0)}, 1).ajustar(y)

    [diagnostico] = coletados
    assert diagnostico.n_treino == N_CURTO_SEMANAL
    assert _situacao(diagnostico, 'estacionariedade') == NAO_TESTAVEL
    assert _situacao(diagnostico, 'dependencia_temporal') == NAO_TESTAVEL
    assert (
        _situacao(diagnostico, 'residuos_sem_autocorrelacao') == NAO_TESTAVEL
    )
    assert _situacao(diagnostico, 'parametros_por_observacao') == ATENDIDA
    assert _situacao(diagnostico, 'raizes_fora_do_circulo') == ATENDIDA


def test_holt_amortecido_com_seis_pontos_excede_a_razao_de_parametros():
    y = _ruido(14, n=N_CURTO_SEMANAL)

    previsor = criar(
        'ets_holt_amortecido', {'phi': 'estimado em [0,8; 0,98]'}, 1
    ).ajustar(y)

    assert (
        _situacao(previsor.diagnostico, 'parametros_por_observacao')
        == NAO_ATENDIDA
    )
    assert np.isfinite(previsor.prever(2)).all()


def test_estacionariedade_e_verificada_apos_a_diferenciacao():
    passeio = np.cumsum(np.random.default_rng(15).normal(0, 1, 200))

    em_nivel = verificar_estacionariedade(passeio, d=0)
    diferenciada = verificar_estacionariedade(passeio, d=1)

    assert em_nivel.situacao == NAO_ATENDIDA
    assert diferenciada.situacao == ATENDIDA
    assert diferenciada.detalhe['d'] == 1
    assert diferenciada.detalhe['n'] == len(passeio) - 1


def test_ljung_box_distingue_ruido_de_dependencia():
    ar = _ar1(16, n=200, phi=0.8)
    ruido = _ruido(16, n=200)

    assert verificar_dependencia(ar, 1).situacao == ATENDIDA
    assert verificar_dependencia(ruido, 1).situacao == INCONCLUSIVA
    assert verificar_residuos(ar, 1, 1).situacao == NAO_ATENDIDA
    assert verificar_residuos(ruido, 1, 1).situacao == ATENDIDA


def test_ljung_box_exige_mais_lags_que_parametros():
    verificacao = verificar_residuos(_ruido(17, n=42), 7, 9)

    assert verificacao.situacao == NAO_TESTAVEL
    assert verificacao.detalhe['lag'] == LAG_MAXIMO_EM_42


def test_sazonalidade_inconclusiva_nao_e_reprovacao():
    com_ciclo = verificar_sazonalidade(_sazonal(18), 7)
    sem_ciclo = verificar_sazonalidade(_ruido(19, n=84), 7)
    curta = verificar_sazonalidade(_sazonal(18, n=34), 7)

    assert com_ciclo.situacao == ATENDIDA
    assert sem_ciclo.situacao == INCONCLUSIVA
    assert curta.situacao == NAO_TESTAVEL


def test_zeros_parametros_e_raizes():
    assert verificar_zeros(np.array([0.0, 1.0])).situacao == NAO_ATENDIDA
    assert verificar_zeros(np.array([2.0, 1.0])).situacao == INCONCLUSIVA
    assert verificar_parametros(6, 3).situacao == ATENDIDA
    assert verificar_parametros(6, 4).situacao == NAO_ATENDIDA
    assert (
        verificar_raizes(np.array([1.002]), np.array([])).situacao
        == NAO_ATENDIDA
    )
    assert (
        verificar_raizes(np.array([2.0]), np.array([1.5])).situacao == ATENDIDA
    )
    assert (
        verificar_raizes(np.array([]), np.array([])).situacao == NAO_TESTAVEL
    )


def _emitir_aviso_de_convergencia():
    warnings.warn('não convergiu', ConvergenceWarning, stacklevel=1)
    return SimpleNamespace()


def _levantar():
    raise np.linalg.LinAlgError('matriz singular')


@pytest.mark.parametrize(
    ('estimar', 'convergiu', 'trecho'),
    [
        (_emitir_aviso_de_convergencia, lambda r: True, 'aviso'),
        (SimpleNamespace, lambda r: False, 'não convergiu'),
        (_levantar, lambda r: True, 'LinAlgError'),
    ],
)
def test_erro_ou_aviso_de_convergencia_vira_falha(estimar, convergiu, trecho):
    with coletar_diagnosticos() as coletados:
        with pytest.raises(FalhaConvergencia, match=trecho) as falha:
            ajustar_monitorado(
                'arima', {'ordem': 1}, N_FALHA, estimar, convergiu
            )

    assert falha.value.n_treino == N_FALHA
    assert falha.value.algoritmo == 'arima'
    assert falha.value.hiperparametros == {'ordem': 1}
    assert [d.convergiu for d in coletados] == [False]
    assert trecho in coletados[0].avisos[0]


def test_serie_constante_nao_converge_e_vira_falha():
    with pytest.raises(FalhaConvergencia, match='arima'):
        criar('arima', {'ordem': (1, 0, 1)}, 1).ajustar(np.full(42, 5.0))


def test_erro_de_programacao_nao_vira_falha():
    with pytest.raises(TypeError):
        ajustar_monitorado('arima', {}, 9, lambda: len(None), lambda r: True)


def test_avisos_que_nao_sao_de_convergencia_ficam_registrados():
    def estimar():
        warnings.warn('início ruim', UserWarning, stacklevel=1)
        warnings.warn('saiu de moda', DeprecationWarning, stacklevel=1)
        return SimpleNamespace()

    _, avisos = ajustar_monitorado('arima', {}, 9, estimar, lambda r: True)

    assert avisos == ('UserWarning: início ruim',)


def test_diagnosticos_sem_coletor_nao_acumulam():
    criar('ets_ses', {'alfa': 'estimado'}, 1).ajustar(_ruido(20))

    assert algoritmos_statsmodels._COLETOR.get() is None


def test_treino_vazio_e_rejeitado():
    with pytest.raises(ValueError, match='treino vazio'):
        criar('ets_ses', {'alfa': 'estimado'}, 1).ajustar([])
