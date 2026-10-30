"""Croston, SBA e TSB: recursões à mão, bordas e propriedades (#10).

Cada `approx` à mão escreve a recursão passo a passo, sem chamar o código
testado. Séries com valores fixos só aparecem nessas contas; as demais são
geradas com semente.
"""

import subprocess
import sys

import cloudpickle
import numpy as np
import pytest

from case_mr_health import algoritmos
from case_mr_health.algoritmos_intermitentes import SBA, TSB, Croston
from case_mr_health.candidatos import SKUS, candidatos

SEED = 20261030
HORIZONTE = 7
METODOS = [
    pytest.param(lambda a: Croston(alfa=a), id='croston'),
    pytest.param(lambda a: SBA(alfa=a), id='sba'),
    pytest.param(lambda a: TSB(alfa_beta=a), id='tsb'),
]


def _taxa(previsor, y):
    return previsor.ajustar(y).prever(1)[0]


def _tamanho(serie_sem_zeros, alfa):
    """Tamanho suavizado, a partir da primeira demanda."""
    z = serie_sem_zeros[0]
    for q in serie_sem_zeros[1:]:
        z = (1 - alfa) * z + alfa * q
    return z


@pytest.fixture
def rng():
    return np.random.default_rng(SEED)


def _intermitente(rng, n, p, tamanho_medio):
    """Demanda Bernoulli(`p`) com tamanho 1 + Poisson(`tamanho_medio` - 1)."""
    return (rng.random(n) < p) * (rng.poisson(tamanho_medio - 1, n) + 1.0)


def test_croston_confere_com_a_recursao_a_mao():
    # Posições 3, 5 e 8; tamanhos 3, 1, 2; intervalos 3, 2, 3 (média 8/3).
    y = [0, 0, 3, 0, 1, 0, 0, 2]
    z = 3 + 0.1 * (1 - 3)  # 2,8
    z += 0.1 * (2 - z)  # 2,72
    x = 8 / 3 + 0.1 * (2 - 8 / 3)  # 2,6
    x += 0.1 * (3 - x)  # 2,64

    assert _taxa(Croston(alfa=0.1), y) == pytest.approx(z / x)
    assert z / x == pytest.approx(2.72 / 2.64)


def test_sba_aplica_o_fator_sobre_a_recursao_a_mao():
    y = [0, 0, 3, 0, 1, 0, 0, 2]

    assert _taxa(SBA(alfa=0.1), y) == pytest.approx(0.95 * 2.72 / 2.64)


def test_tsb_confere_com_a_recursao_a_mao():
    # Ocorrência 0,0,1,0,1,0,0,1; p parte de 3/8 e usa do 2º período em diante.
    y = [0, 0, 3, 0, 1, 0, 0, 2]
    p = 3 / 8
    for ocorreu in (0, 1, 0, 1, 0, 0, 1):
        p += 0.1 * (ocorreu - p)

    assert p == pytest.approx(0.4113103375)
    assert _taxa(TSB(alfa_beta=0.1), y) == pytest.approx(p * 2.72)


def test_demanda_no_primeiro_e_no_ultimo_periodo_confere_a_mao():
    # Posições 1, 4 e 5; tamanhos 2, 4, 1; intervalos 1, 3, 1 (média 5/3).
    y = [2, 0, 0, 4, 1]
    alfa = 0.2
    z = 2 + alfa * (4 - 2)  # 2,4
    z += alfa * (1 - z)  # 2,12
    x = 5 / 3 + alfa * (3 - 5 / 3)
    x += alfa * (1 - x)
    p = 3 / 5
    for ocorreu in (0, 0, 1, 1):
        p += alfa * (ocorreu - p)

    assert _taxa(Croston(alfa=alfa), y) == pytest.approx(z / x)
    assert _taxa(SBA(alfa=alfa), y) == pytest.approx(0.9 * z / x)
    assert p == pytest.approx(0.60576)
    assert _taxa(TSB(alfa_beta=alfa), y) == pytest.approx(p * 2.12)


@pytest.mark.parametrize('metodo', METODOS)
@pytest.mark.parametrize('n', [1, 5, 42])
def test_treino_so_de_zeros_preve_zero(metodo, n):
    previsao = metodo(0.2).ajustar(np.zeros(n)).prever(HORIZONTE)

    assert previsao.tolist() == [0.0] * HORIZONTE


def test_uma_demanda_no_primeiro_periodo_ignora_os_zeros_seguintes():
    y = [5, 0, 0, 0]

    assert _taxa(Croston(alfa=0.1), y) == pytest.approx(5)  # 5 / 1
    assert _taxa(SBA(alfa=0.1), y) == pytest.approx(0.95 * 5)
    assert _taxa(TSB(alfa_beta=0.1), y) == pytest.approx(5 * 0.25 * 0.9**3)


def test_uma_demanda_no_ultimo_periodo():
    y = [0, 0, 0, 5]

    assert _taxa(Croston(alfa=0.1), y) == pytest.approx(5 / 4)
    assert _taxa(SBA(alfa=0.1), y) == pytest.approx(0.95 * 5 / 4)
    p = 0.25 * 0.9**3 + 0.1  # 0,25 -> 0,225 -> 0,2025 -> 0,28225
    assert _taxa(TSB(alfa_beta=0.1), y) == pytest.approx(5 * p)


def test_uma_demanda_no_meio():
    y = [0, 0, 6, 0, 0]

    assert _taxa(Croston(alfa=0.3), y) == pytest.approx(6 / 3)
    assert _taxa(SBA(alfa=0.3), y) == pytest.approx(0.85 * 6 / 3)
    p = 0.2 * 0.7
    p += 0.3 * (1 - p)
    p *= 0.7**2
    assert _taxa(TSB(alfa_beta=0.3), y) == pytest.approx(6 * p)


def test_treino_de_um_unico_periodo():
    assert _taxa(Croston(alfa=0.1), [4]) == pytest.approx(4)
    assert _taxa(TSB(alfa_beta=0.1), [4]) == pytest.approx(4)
    assert _taxa(SBA(alfa=0.1), [0]) == 0


def test_serie_sem_zeros_recupera_o_nivel(rng):
    nivel = rng.integers(1, 20)
    y = np.full(30, float(nivel))

    assert _taxa(Croston(alfa=0.2), y) == pytest.approx(nivel)
    assert _taxa(SBA(alfa=0.2), y) == pytest.approx(0.9 * nivel)
    assert _taxa(TSB(alfa_beta=0.2), y) == pytest.approx(nivel)


@pytest.mark.parametrize('metodo', METODOS)
@pytest.mark.parametrize('alfa', [0.1, 0.2, 0.3, 1])
def test_previsao_e_constante_e_nao_negativa(metodo, alfa, rng):
    for _ in range(200):
        n = int(rng.integers(1, 80))
        y = _intermitente(rng, n, rng.uniform(0.05, 1), 4)

        previsao = metodo(alfa).ajustar(y).prever(HORIZONTE)

        assert previsao.shape == (HORIZONTE,)
        assert np.isfinite(previsao).all()
        assert (previsao >= 0).all()
        assert (previsao == previsao[0]).all()


def test_sba_e_o_croston_com_o_fator(rng):
    for alfa in (0.1, 0.2, 0.3):
        y = _intermitente(rng, 60, 0.5, 3)

        assert _taxa(SBA(alfa=alfa), y) == pytest.approx(
            (1 - alfa / 2) * _taxa(Croston(alfa=alfa), y)
        )


@pytest.mark.parametrize('metodo', METODOS)
def test_reajustar_nao_guarda_estado(metodo, rng):
    y = _intermitente(rng, 50, 0.5, 3)
    limpo = _taxa(metodo(0.2), y)

    previsor = metodo(0.2).ajustar(_intermitente(rng, 50, 0.3, 9))

    assert _taxa(previsor, y) == limpo


def test_tamanho_so_e_atualizado_com_demanda(rng):
    tamanhos = rng.integers(1, 9, 4).astype(float)
    com_zeros = np.zeros(10)
    com_zeros[[0, 3, 4, 7]] = tamanhos
    p = 4 / 10
    for ocorreu in (0, 0, 1, 1, 0, 0, 1, 0, 0):
        p += 0.2 * (ocorreu - p)

    assert _taxa(TSB(alfa_beta=0.2), com_zeros) == pytest.approx(
        p * _tamanho(tamanhos, 0.2)
    )


def test_tsb_decai_depois_da_ultima_demanda_e_croston_nao(rng):
    ativa = _intermitente(rng, 60, 0.5, 3)
    obsoleta = np.concatenate([ativa, np.zeros(30)])

    croston = Croston(alfa=0.2)

    assert _taxa(croston, obsoleta) == _taxa(croston, ativa)
    assert _taxa(TSB(alfa_beta=0.2), obsoleta) < (
        0.05 * _taxa(TSB(alfa_beta=0.2), ativa)
    )


@pytest.mark.parametrize('metodo', METODOS)
@pytest.mark.parametrize(
    'y',
    [[], [1, -1, 2], [1, float('nan'), 2]],
    ids=['vazio', 'negativa', 'ausente'],
)
def test_treino_invalido_e_rejeitado(metodo, y):
    with pytest.raises(ValueError, match='treino'):
        metodo(0.1).ajustar(y)


@pytest.mark.parametrize('metodo', METODOS)
@pytest.mark.parametrize('alfa', [0, -0.1, 1.1])
def test_parametro_de_suavizacao_fora_do_intervalo(metodo, alfa):
    with pytest.raises(ValueError, match='deve estar em'):
        metodo(alfa)


def test_sba_tem_menos_vies_que_croston_e_tsb_fica_perto_da_taxa(rng):
    """Taxa verdadeira 0,25 x 3 = 0,75; 400 séries longas estacionárias."""
    taxa, alfa = 0.75, 0.2
    series = [_intermitente(rng, 400, 0.25, 3) for _ in range(400)]

    croston = np.mean([_taxa(Croston(alfa=alfa), y) for y in series])
    sba = np.mean([_taxa(SBA(alfa=alfa), y) for y in series])
    tsb = np.mean([_taxa(TSB(alfa_beta=alfa), y) for y in series])

    assert croston > taxa
    assert abs(sba - taxa) < abs(croston - taxa)
    assert tsb == pytest.approx(taxa, abs=0.07)


def test_iniciar_pela_media_reduz_o_vies_no_treino_de_42_dias(rng):
    """Calendário começa em venda: o primeiro intervalo é sempre 1."""
    alfa, n = 0.1, 42
    taxa = 0.6 * 3

    def croston_primeiro_intervalo(y):
        posicoes = np.flatnonzero(y)
        x = 1.0
        for intervalo in np.diff(posicoes):
            x += alfa * (intervalo - x)
        return _tamanho(y[posicoes], alfa) / x

    pela_media, pelo_primeiro = [], []
    for _ in range(3000):
        y = _intermitente(rng, n, 0.6, 3)
        y[0] = rng.poisson(2) + 1.0
        pela_media.append(_taxa(Croston(alfa=alfa), y))
        pelo_primeiro.append(croston_primeiro_intervalo(y))

    assert abs(np.mean(pela_media) - taxa) < abs(np.mean(pelo_primeiro) - taxa)


@pytest.mark.parametrize('sku', SKUS)
def test_candidatos_da_diaria_instanciam_com_o_espaco_da_tabela(sku, rng):
    intermitentes = [
        c for c in candidatos(sku, 'diaria') if c.familia == 'intermitente'
    ]

    assert {c.algoritmo for c in intermitentes} == {'croston', 'sba', 'tsb'}
    y = _intermitente(rng, 42, 0.6, 3)
    for candidato in intermitentes:
        combinacoes = candidato.combinacoes()
        assert len(combinacoes) == 3  # noqa: PLR2004
        for hiperparametros in combinacoes:
            previsor = algoritmos.criar(
                candidato.algoritmo, hiperparametros, SEED
            )
            assert len(previsor.ajustar(y).prever(HORIZONTE)) == HORIZONTE


@pytest.mark.parametrize('metodo', METODOS)
def test_previsor_ajustado_sobrevive_ao_cloudpickle(metodo, rng):
    y = _intermitente(rng, 42, 0.6, 3)
    previsor = metodo(0.2).ajustar(y)

    copia = cloudpickle.loads(cloudpickle.dumps(previsor))

    assert copia.prever(3).tolist() == previsor.prever(3).tolist()


def test_importar_o_modulo_primeiro_registra_os_tres():
    codigo = (
        'import case_mr_health.algoritmos_intermitentes as m;'
        'from case_mr_health.algoritmos import ALGORITMOS as a;'
        "assert {'croston', 'sba', 'tsb'} <= set(a)"
    )

    subprocess.run([sys.executable, '-c', codigo], check=True)  # noqa: S603
