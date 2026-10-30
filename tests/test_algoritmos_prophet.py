from types import SimpleNamespace

import cloudpickle
import numpy as np
import pytest

from case_mr_health import algoritmos_prophet
from case_mr_health.algoritmos import criar
from case_mr_health.algoritmos_prophet import ProphetSemanal
from case_mr_health.algoritmos_statsmodels import (
    FalhaConvergencia,
    coletar_diagnosticos,
)
from case_mr_health.candidatos import ATENDIDA

HP = {'ordem_fourier': 3, 'escala_sazonalidade': 10.0}
HORIZONTE = 14
TOLERANCIA_ANCORA = 1e-4
SEED = 20261030
PERIODO = 7


def _sazonal(seed: int, n: int = 70, inicio: int = 0) -> np.ndarray:
    """Ciclo de 7 dias; `inicio` desloca a fase, como outro início de série."""
    rng = np.random.default_rng(seed)
    padrao = np.array([1, 1, 2, 2, 8, 9, 7], dtype=float)
    return padrao[(np.arange(n) + inicio) % 7] + rng.normal(0, 0.3, n)


def test_criar_repassa_a_seed():
    previsor = criar('prophet', HP, seed=SEED)

    assert isinstance(previsor, ProphetSemanal)
    assert previsor.seed == SEED


def test_usa_so_sazonalidade_semanal_e_tendencia_sem_mudancas():
    previsor = criar('prophet', HP, 1).ajustar(_sazonal(1))
    modelo = previsor._modelo

    assert set(modelo.seasonalities) == {'weekly'}
    semanal = modelo.seasonalities['weekly']
    assert semanal['fourier_order'] == HP['ordem_fourier']
    assert semanal['period'] == PERIODO
    assert semanal['prior_scale'] == HP['escala_sazonalidade']
    assert semanal['mode'] == 'additive'
    assert modelo.n_changepoints == 0
    assert modelo.growth == 'linear'
    assert modelo.holidays is None


@pytest.mark.parametrize('inicio', ['2021-06-02', '2021-06-05', '2021-06-08'])
def test_previsao_nao_depende_do_inicio_do_calendario(monkeypatch, inicio):
    y = _sazonal(2)
    referencia = criar('prophet', HP, 1).ajustar(y).prever(HORIZONTE)

    monkeypatch.setattr(algoritmos_prophet, 'INICIO_CALENDARIO', inicio)
    deslocada = criar('prophet', HP, 1).ajustar(y).prever(HORIZONTE)

    assert np.abs(referencia - deslocada).max() < TOLERANCIA_ANCORA


@pytest.mark.parametrize('deslocamento', range(7))
def test_previsao_recupera_a_fase_da_serie(deslocamento):
    y = _sazonal(3, inicio=deslocamento)

    previsao = criar('prophet', HP, 1).ajustar(y).prever(7)

    padrao = np.array([1, 1, 2, 2, 8, 9, 7], dtype=float)
    fase = (np.arange(len(y), len(y) + 7) + deslocamento) % 7
    assert np.argmax(previsao) == np.argmax(padrao[fase])
    assert np.abs(previsao - padrao[fase]).max() < 1


def test_mesma_seed_reproduz_previsao_e_intervalos():
    y = _sazonal(4)

    uma = criar('prophet', HP, 7).ajustar(y)
    outra = criar('prophet', HP, 7).ajustar(y)

    assert np.array_equal(uma.prever(7), outra.prever(7))
    a = uma.intervalos_nativos(7, (0.8, 0.95))
    b = outra.intervalos_nativos(7, (0.8, 0.95))
    assert np.array_equal(a[0.95][0], b[0.95][0])
    assert np.array_equal(a[0.8][1], b[0.8][1])


def test_intervalos_nao_mexem_no_gerador_global():
    previsor = criar('prophet', HP, 7).ajustar(_sazonal(5))
    np.random.seed(1)  # noqa: NPY002
    esperado = np.random.random()  # noqa: NPY002

    np.random.seed(1)  # noqa: NPY002
    previsor.intervalos_nativos(7, (0.8,))

    assert np.random.random() == esperado  # noqa: NPY002


def test_intervalos_contem_a_previsao_e_aninham_os_niveis():
    previsor = criar('prophet', HP, 7).ajustar(_sazonal(6))
    previsao = previsor.prever(HORIZONTE)

    intervalos = previsor.intervalos_nativos(HORIZONTE, (0.8, 0.95))

    baixo_80, alto_80 = intervalos[0.8]
    baixo_95, alto_95 = intervalos[0.95]
    assert (baixo_95 < baixo_80).all()
    assert (baixo_80 < previsao).all()
    assert (previsao < alto_80).all()
    assert (alto_80 < alto_95).all()


def test_previsor_serializado_e_pequeno_sem_caminhos_e_preve_igual():
    previsor = criar('prophet', HP, 7).ajustar(_sazonal(7))

    binario = cloudpickle.dumps(previsor)
    carregado = cloudpickle.loads(binario)

    assert len(binario) < 50_000  # noqa: PLR2004
    assert b'prophet_model.bin' not in binario
    assert b'stan_fit' not in binario
    assert np.array_equal(carregado.prever(7), previsor.prever(7))
    assert np.array_equal(
        carregado.intervalos_nativos(7, (0.8,))[0.8][0],
        previsor.intervalos_nativos(7, (0.8,))[0.8][0],
    )


def test_previsor_sem_ajuste_tambem_serializa():
    carregado = cloudpickle.loads(cloudpickle.dumps(criar('prophet', HP, 7)))

    assert carregado.ordem_fourier == HP['ordem_fourier']


def test_serie_constante_nao_passa_pelo_stan():
    previsor = criar('prophet', HP, 7).ajustar(np.full(42, 5.0))

    assert np.allclose(previsor.prever(3), 5.0)


def test_diagnostico_verifica_a_sazonalidade():
    with coletar_diagnosticos() as coletados:
        criar('prophet', HP, 7).ajustar(_sazonal(8))

    [diagnostico] = coletados
    assert diagnostico.convergiu
    assert [p.premissa for p in diagnostico.premissas] == ['sazonalidade']
    assert diagnostico.premissas[0].situacao == ATENDIDA


def test_erro_do_stan_vira_falha(monkeypatch):
    def estimar(self, y):
        raise RuntimeError('Error during optimization')

    monkeypatch.setattr(ProphetSemanal, '_estimar', estimar)

    with coletar_diagnosticos() as coletados:
        with pytest.raises(FalhaConvergencia, match='RuntimeError'):
            criar('prophet', HP, 7).ajustar(_sazonal(9))
    assert [d.convergiu for d in coletados] == [False]


def test_otimizador_que_nao_converge_vira_falha(monkeypatch):
    modelo = SimpleNamespace(
        stan_backend=SimpleNamespace(stan_fit=SimpleNamespace(converged=False))
    )
    monkeypatch.setattr(ProphetSemanal, '_estimar', lambda self, y: modelo)

    with pytest.raises(FalhaConvergencia, match='não convergiu'):
        criar('prophet', HP, 7).ajustar(_sazonal(10))
