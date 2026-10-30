import numpy as np
import pytest

from case_mr_health.diagnosticos import (
    bootstrap_blocos,
    estacionariedade,
    intermitencia,
    proporcao_zeros,
    razao_fim_de_semana,
    sazonalidade_semanal,
    sinalizar_outliers,
)

SEMANAS = 12
ALFA = 0.05
ALFA_FORTE = 0.01
INDICE_OUTLIER = 8


@pytest.fixture
def rng():
    return np.random.default_rng(7)


@pytest.fixture
def semanas_com_pico_no_fim_de_semana(rng):
    base = rng.poisson(1, size=(SEMANAS, 7)).astype(float)
    base[:, 4:] += rng.poisson(5, size=(SEMANAS, 3))
    return base


@pytest.fixture
def semanas_sem_sazonalidade(rng):
    return rng.poisson(3, size=(SEMANAS, 7)).astype(float)


def test_proporcao_zeros_e_intervalo():
    y = np.array([0, 0, 0, 1, 2, 0, 3, 0, 0, 4])

    p, baixo, alto = proporcao_zeros(y)

    assert p == pytest.approx(0.6)
    assert 0 < baixo < p < alto < 1


@pytest.mark.parametrize(
    ('y', 'classe'),
    [
        ([4, 5, 4, 5] * 10, 'suave'),
        ([1, 10, 2, 20] * 10, 'errática'),
        (([0, 0, 0, 4]) * 10, 'intermitente'),
        (([0, 0, 0, 1, 0, 0, 0, 20]) * 5, 'irregular'),
    ],
)
def test_classificacao_de_syntetos_boylan_croston(y, classe):
    assert intermitencia(np.array(y)).classe == classe


def test_adi_e_cv2_calculados_a_mao():
    r = intermitencia(np.array([0, 2, 0, 0, 4, 0]))

    assert r.adi == pytest.approx(3.0)
    assert r.cv2 == pytest.approx((1 / 3) ** 2)


def test_razao_fim_de_semana_calculada_a_mao():
    m = np.array([[1, 1, 1, 1, 2, 2, 2.0], [1, 1, 1, 1, 4, 4, 4.0]])

    assert razao_fim_de_semana(m) == pytest.approx(3.0)


def test_sazonalidade_detectada_quando_ha_pico_no_fim_de_semana(
    semanas_com_pico_no_fim_de_semana,
):
    r = sazonalidade_semanal(semanas_com_pico_no_fim_de_semana, n_perm=2000)

    assert r['kruskal_p'] < ALFA_FORTE
    assert r['permutacao_p'] < ALFA_FORTE


def test_sazonalidade_nao_detectada_em_serie_sem_padrao(
    semanas_sem_sazonalidade,
):
    r = sazonalidade_semanal(semanas_sem_sazonalidade, n_perm=2000)

    assert r['kruskal_p'] > ALFA
    assert r['permutacao_p'] > ALFA


def test_bootstrap_cobre_o_valor_observado(
    semanas_com_pico_no_fim_de_semana,
):
    obs, baixo, alto = bootstrap_blocos(
        semanas_com_pico_no_fim_de_semana,
        razao_fim_de_semana,
        n_boot=1000,
    )

    assert baixo <= obs <= alto


def test_estacionariedade_nao_testavel_com_amostra_curta(rng):
    assert not estacionariedade(rng.normal(size=10))['testavel']


def test_estacionariedade_distingue_ruido_de_passeio_aleatorio(rng):
    ruido = estacionariedade(rng.normal(size=200))
    passeio = estacionariedade(rng.normal(size=200).cumsum())

    assert ruido['veredito'] == 'estacionária'
    assert passeio['veredito'] != 'estacionária'


def test_outlier_e_sinalizado_so_entre_os_nao_nulos():
    y = np.array([0, 3, 4, 0, 3, 4, 3, 0, 40, 4, 3, 0.0])

    r = sinalizar_outliers(y)

    assert r['mad'] == [INDICE_OUTLIER]
    assert INDICE_OUTLIER in r['iqr']
