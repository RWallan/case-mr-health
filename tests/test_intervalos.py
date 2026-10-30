from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from case_mr_health import algoritmos, intervalos
from case_mr_health.backtest import rodar_backtest
from case_mr_health.candidatos import tabela
from case_mr_health.intervalos import (
    AMOSTRA_INSUFICIENTE,
    CALIBRADO,
    FORA_DA_FAIXA,
    INDISPONIVEL,
    QUANTIL,
    SEM_NATIVO,
    STUDENT,
    Cobertura,
    ConfigIntervalos,
    calibrar,
    contar,
    decidir_nativo,
    fracao_zeros,
    minimo_de_erros,
    normalizar,
    rotulo,
    tem_piso_zero,
    wilson,
)
from case_mr_health.particoes import Fold, Particao

INICIO = date(2021, 6, 7)  # segunda-feira
NIVEIS = (0.80, 0.95)
CONFIG = ConfigIntervalos(NIVEIS)
SEED = 20211
N_REPLICAS = 1500
N_PONTOS_DIARIA = 28
SEMANA_ATIPICA = 6


def _particao(sku, gran, n, treino_min, passo) -> Particao:
    unidade = timedelta(weeks=1) if gran == 'semanal' else timedelta(days=1)
    ultimo = timedelta(days=6) if gran == 'semanal' else timedelta(0)
    datas = [INICIO + i * unidade for i in range(n)]
    folds = tuple(
        Fold(
            datas[0],
            datas[t - 1] + ultimo,
            datas[t],
            datas[t + passo - 1] + ultimo,
        )
        for t in range(treino_min, n - passo + 1, passo)
    )
    return Particao(
        sku, gran, datas[0], datas[-1] + ultimo, datas[-1], datas[-1], folds
    )


def _serie(valores, gran) -> pd.Series:
    freq = 'W-MON' if gran == 'semanal' else 'D'
    indice = pd.date_range(INICIO, periods=len(valores), freq=freq)
    return pd.Series(valores, index=indice, dtype=float)


def _fabrica(classe=algoritmos.MediaHistorica, **kwargs):
    return lambda: classe(**kwargs)


class Zero:
    """Previsão sempre zero: o erro é o próprio valor observado."""

    def ajustar(self, y):
        return self

    @staticmethod
    def prever(horizonte):
        return np.zeros(horizonte)


@pytest.fixture
def rng():
    return np.random.default_rng(SEED)


def test_rotulo_do_nivel():
    assert rotulo(0.8) == '80'
    assert rotulo(0.95) == '95'
    assert rotulo(0.975) == '97.5'


@pytest.mark.parametrize('niveis', [(), (0.0, 0.5), (0.8, 1.0)])
def test_niveis_invalidos_sao_rejeitados(niveis):
    with pytest.raises(ValueError, match='níveis inválidos'):
        ConfigIntervalos(niveis)


def test_max_origens_invalido_e_rejeitado():
    with pytest.raises(ValueError, match='max_origens'):
        ConfigIntervalos(NIVEIS, max_origens=0)


def test_normalizar_garante_as_propriedades_em_limites_arbitrarios(rng):
    # Limites brutos propositalmente ruins: negativos, sem aninhar e sem
    # conter a previsão.
    for _ in range(200):
        previsto = rng.normal(1, 3, 7)
        brutos = {
            n: (rng.normal(-1, 4, 7), rng.normal(1, 4, 7)) for n in NIVEIS
        }

        limites = normalizar(previsto, brutos)

        ponto = np.clip(previsto, 0, None)
        inf80, sup80 = limites[0.80]
        inf95, sup95 = limites[0.95]
        assert (inf80 >= 0).all()
        assert (inf95 >= 0).all()
        assert (sup80 >= 0).all()
        assert (inf95 <= inf80).all()
        assert (sup95 >= sup80).all()
        assert (inf80 <= ponto).all()
        assert (sup80 >= ponto).all()


def test_normalizar_nao_altera_limites_ja_validos():
    previsto = np.array([2.0, 3.0])
    brutos = {
        0.80: (np.array([1.0, 2.0]), np.array([3.0, 4.0])),
        0.95: (np.array([0.5, 1.0]), np.array([5.0, 6.0])),
    }

    limites = normalizar(previsto, brutos)

    for nivel, par in brutos.items():
        assert limites[nivel][0].tolist() == par[0].tolist()
        assert limites[nivel][1].tolist() == par[1].tolist()


def _brutos_positivos(h=3):
    return {
        0.80: (np.full(h, 1.0), np.full(h, 4.0)),
        0.95: (np.full(h, 0.5), np.full(h, 6.0)),
    }


@pytest.mark.parametrize(
    ('zeros', 'total', 'nivel', 'esperado'),
    [
        (1, 10, 0.80, True),  # fronteira exata: 0,10 = (1 - 0,80) / 2
        (9, 100, 0.80, False),  # logo abaixo
        (11, 100, 0.80, True),  # logo acima
        (1, 40, 0.95, True),  # fronteira exata: 0,025 = (1 - 0,95) / 2
        (2, 100, 0.95, False),  # logo abaixo
        (3, 100, 0.95, True),  # logo acima
        (0, 10, 0.95, False),
    ],
)
def test_fronteira_da_fracao_de_zeros(zeros, total, nivel, esperado):
    y = np.concatenate([np.zeros(zeros), np.ones(total - zeros)])

    assert tem_piso_zero(nivel, fracao_zeros(y)) is esperado


def test_piso_vale_so_para_o_nivel_que_atinge_a_fronteira():
    # 5% de zeros: passa em 95% (0,025) e não em 80% (0,10).
    previsto = np.full(3, 2.0)

    limites = normalizar(previsto, _brutos_positivos(), 0.05)

    assert limites[0.95][0].tolist() == [0, 0, 0]
    assert limites[0.80][0].tolist() == [1, 1, 1]


def test_piso_nos_dois_niveis_mantem_superior_e_propriedades():
    previsto = np.full(3, 2.0)
    brutos = _brutos_positivos()

    limites = normalizar(previsto, brutos, 0.40)

    for nivel in NIVEIS:
        assert limites[nivel][0].tolist() == [0, 0, 0]
        assert limites[nivel][1].tolist() == brutos[nivel][1].tolist()
    assert (limites[0.95][1] >= limites[0.80][1]).all()
    assert (limites[0.80][0] <= previsto).all()


def test_sem_zeros_nao_ha_piso():
    previsto = np.full(3, 2.0)
    brutos = _brutos_positivos()

    limites = normalizar(previsto, brutos, 0.0)

    assert limites[0.95][0].tolist() == brutos[0.95][0].tolist()


def test_piso_nao_inventa_limite_em_metodo_indisponivel():
    previsto = np.ones(2)
    nan = np.full(2, np.nan)

    limites = normalizar(previsto, {0.95: (nan, nan)}, 0.5)

    assert np.isnan(limites[0.95][0]).all()


@pytest.mark.parametrize(('nivel', 'esperado'), [(0.80, 9), (0.95, 39)])
def test_minimo_de_erros_confere_com_a_conta(nivel, esperado):
    assert minimo_de_erros(nivel) == esperado


def test_quantis_conferem_com_as_estatisticas_de_ordem():
    # 39 origens, 1 passo; a última origem é 39 + 2 - 1 = 40. Erros 1..39.
    y = np.concatenate([[0.0, 0.0], np.arange(1.0, 40.0)])

    calibracao = calibrar(_fabrica(Zero), y, 1, ConfigIntervalos(NIVEIS, 39))

    assert calibracao.metodo == QUANTIL
    assert calibracao.n_erros == minimo_de_erros(0.95)
    # 95%: k = floor(40 * 0,05 / 2) = 1. 80%: k = floor(40 * 0,2 / 2) = 4.
    assert calibracao.deslocamentos[0.95] == (1.0, 39.0)
    assert calibracao.deslocamentos[0.80] == (4.0, 36.0)


def test_student_confere_com_a_conta():
    # Erros 1, 2, 3, 4: média 2,5; s = 1,29099; 4 origens, gl = 3.
    y = np.array([0.0, 0.0, 1.0, 2.0, 3.0, 4.0])

    calibracao = calibrar(_fabrica(Zero), y, 1, CONFIG)

    assert calibracao.metodo == STUDENT
    meia = 3.18245 * 1.29099 * 1.11803
    baixo, alto = calibracao.deslocamentos[0.95]
    assert baixo == pytest.approx(2.5 - meia, abs=1e-3)
    assert alto == pytest.approx(2.5 + meia, abs=1e-3)


@pytest.mark.parametrize(
    ('n', 'h', 'metodo', 'origens', 'erros'),
    [
        (42, 7, QUANTIL, 34, 238),  # diária, fold 1
        (79, 14, QUANTIL, 64, 896),  # diária, modelo final
        (6, 1, STUDENT, 4, 4),  # semanal, fold 1
        (9, 1, STUDENT, 7, 7),  # semanal, fold 4
        (10, 2, STUDENT, 7, 14),  # semanal, modelo final
        (3, 2, INDISPONIVEL, 0, 0),
    ],
)
def test_metodo_depende_so_do_tamanho_da_amostra(  # noqa: PLR0913, PLR0917
    rng, n, h, metodo, origens, erros
):
    y = rng.poisson(3, n).astype(float)

    calibracao = calibrar(_fabrica(), y, h, CONFIG)

    assert calibracao.metodo == metodo
    assert calibracao.n_origens == origens
    assert calibracao.n_erros == erros


def test_cada_origem_ve_so_o_passado_e_preve_de_uma_vez():
    vistos, horizontes = [], []

    class Espiao(Zero):
        def ajustar(self, y):
            vistos.append(len(y))
            return self

        @staticmethod
        def prever(horizonte):
            horizontes.append(horizonte)
            return np.zeros(horizonte)

    calibrar(Espiao, np.ones(12), 3, CONFIG)

    assert vistos == list(range(2, 10))
    assert set(horizontes) == {3}


def test_origens_sao_limitadas_as_mais_recentes():
    vistos = []

    class Espiao(Zero):
        def ajustar(self, y):
            vistos.append(len(y))
            return self

    calibrar(Espiao, np.ones(50), 7, ConfigIntervalos(NIVEIS, 5))

    assert vistos == [39, 40, 41, 42, 43]


def test_origem_que_falha_e_pulada_e_contada():
    class Fragil(Zero):
        def ajustar(self, y):
            if len(y) < 4:  # noqa: PLR2004
                raise ArithmeticError('sem convergência')
            return self

    calibracao = calibrar(Fragil, np.arange(8.0), 1, CONFIG)

    assert (calibracao.n_falhas, calibracao.n_origens) == (2, 4)


def test_previsao_nao_finita_conta_como_falha():
    class Explode(Zero):
        @staticmethod
        def prever(horizonte):
            return np.full(horizonte, np.nan)

    calibracao = calibrar(Explode, np.arange(8.0), 1, CONFIG)

    assert calibracao.metodo == INDISPONIVEL
    assert calibracao.n_falhas == len(range(2, 8))


def test_indisponivel_gera_nan_e_fica_fora_da_cobertura():
    calibracao = calibrar(_fabrica(), np.ones(3), 2, CONFIG)
    previsao = np.ones(2)

    limites = normalizar(previsao, calibracao.limites(Zero(), previsao, 2))

    assert np.isnan(limites[0.95][0]).all()
    assert contar([1.0, 1.0], *limites[0.95]) == Cobertura(0, 0)


def test_erros_de_varios_passos_alargam_o_intervalo_no_passeio_aleatorio(rng):
    # Com a raiz do passo, h = 14 tem de ser mais largo que h = 1: resíduos
    # de um passo subestimariam o erro no horizonte longo.
    razoes = []
    for _ in range(50):
        y = 50 + np.cumsum(rng.normal(0, 1, 200))
        um_passo = calibrar(_fabrica(algoritmos.Naive), y, 1, CONFIG)
        longo = calibrar(_fabrica(algoritmos.Naive), y, 14, CONFIG)
        largura = [
            c.deslocamentos[0.80][1] - c.deslocamentos[0.80][0]
            for c in (um_passo, longo)
        ]
        razoes.append(largura[1] / largura[0])

    assert np.median(razoes) > 1.5  # noqa: PLR2004


def test_horizonte_acima_do_calibrado_e_rejeitado():
    calibracao = calibrar(_fabrica(), np.arange(20.0), 2, CONFIG)

    with pytest.raises(ValueError, match='acima do calibrado'):
        calibracao.limites(Zero(), np.zeros(3), 3)


def test_contar_e_inclusivo_nas_pontas():
    cobertura = contar(
        [0.0, 1.0, 2.0, 3.0],
        np.array([0.0, 0.0, 0.0, 0.0]),
        np.array([2.0, 2.0, 2.0, 2.0]),
    )

    assert cobertura == Cobertura(3, 4)
    assert cobertura.valor == pytest.approx(0.75)


def test_cobertura_vazia_e_indefinida():
    assert np.isnan(Cobertura(0, 0).valor)
    assert np.isnan(Cobertura(0, 0).ic[0])


def test_cobertura_com_distribuicao_conhecida_e_a_nominal(rng):
    # Limites nos quantis verdadeiros de N(0, 1): a contagem recupera 80% e
    # 95% (erro-padrão menor que 0,003 com 20 mil pontos).
    observado = rng.normal(0, 1, 20_000)
    for nivel in NIVEIS:
        z = stats.norm.ppf(1 - (1 - nivel) / 2)
        inferior = np.full(observado.size, -z)
        superior = np.full(observado.size, z)

        assert contar(observado, inferior, superior).valor == pytest.approx(
            nivel, abs=0.01
        )


@pytest.mark.parametrize(
    ('k', 'n', 'baixo', 'alto'),
    [(4, 4, 0.5101, 1.0), (3, 4, 0.3006, 0.9544), (0, 4, 0.0, 0.4899)],
)
def test_wilson_confere_com_a_conta(k, n, baixo, alto):
    assert wilson(k, n) == pytest.approx((baixo, alto), abs=1e-3)


@pytest.mark.parametrize(
    ('k80', 'k95', 'n', 'usar', 'motivo'),
    [
        (22, 27, N_PONTOS_DIARIA, True, CALIBRADO),
        (4, 4, 4, False, AMOSTRA_INSUFICIENTE),
        (15, 27, N_PONTOS_DIARIA, False, FORA_DA_FAIXA),  # R3: 54%
        (20, 27, N_PONTOS_DIARIA, False, FORA_DA_FAIXA),  # só R4: 71%
        (28, 28, N_PONTOS_DIARIA, False, FORA_DA_FAIXA),  # R3: excesso
    ],
)
def test_regra_do_nativo(k80, k95, n, usar, motivo):
    coberturas = {0.80: Cobertura(k80, n), 0.95: Cobertura(k95, n)}

    assert decidir_nativo(coberturas) == (usar, motivo)


def test_sem_nativo():
    assert decidir_nativo(None) == (False, SEM_NATIVO)


def _coberturas_simuladas(rng, gerar, n, h, nivel):
    """Cobertura real do procedimento em réplicas de um processo conhecido."""
    dentro = 0
    for _ in range(N_REPLICAS):
        y = gerar(rng, n + h)
        treino, futuro = y[:n], y[n:]
        calibracao = calibrar(_fabrica(), treino, h, CONFIG)
        previsto = np.full(h, treino.mean())
        limites = normalizar(previsto, calibracao.limites(Zero(), previsto, h))
        dentro += contar(futuro, *limites[nivel]).k
    return dentro / (N_REPLICAS * h)


def _normal(rng, n):
    return rng.normal(20, 4, n)


def _poisson(rng, n):
    return rng.poisson(1.5, n).astype(float)


@pytest.mark.parametrize(
    ('gerar', 'n', 'h', 'nivel'),
    [
        (_normal, 42, 7, 0.80),  # como na diária (quantis)
        (_normal, 42, 7, 0.95),
        (_poisson, 42, 7, 0.80),  # intermitente discreta
        (_poisson, 42, 7, 0.95),
        (_normal, 9, 1, 0.80),  # como na semanal (t)
        (_normal, 9, 1, 0.95),
    ],
)
def test_procedimento_cobre_o_nominal_em_processo_estavel(
    rng, gerar, n, h, nivel
):
    # Não é garantia formal: a tolerância é de 3 pontos para baixo. Valores
    # observados na seção de fatos de docs/relatorio/fase2/8.md.
    cobertura = _coberturas_simuladas(rng, gerar, n, h, nivel)

    assert cobertura >= nivel - 0.03  # noqa: PLR2004
    assert cobertura <= 1


class NativoFalso(algoritmos.MediaHistorica):
    """Intervalo nativo com largura controlada pelo teste."""

    meia_largura = 1.0

    def intervalos_nativos(self, horizonte, niveis):
        return {
            n: (
                np.full(horizonte, self._media - self.meia_largura * n),
                np.full(horizonte, self._media + self.meia_largura * n),
            )
            for n in niveis
        }


class NativoQuebrado(algoritmos.MediaHistorica):
    @staticmethod
    def intervalos_nativos(horizonte, niveis):
        return {n: (np.ones(horizonte), np.zeros(horizonte)) for n in niveis}


class NativoComErro(algoritmos.MediaHistorica):
    @staticmethod
    def intervalos_nativos(horizonte, niveis):
        raise ArithmeticError('sem variância')


def _backtest(valores, nome, gran='diaria', passo=7, treino_min=42):
    particao = _particao('item A', gran, len(valores), treino_min, passo)
    return rodar_backtest(
        _serie(valores, gran), particao, nome, {}, SEED, CONFIG
    )


@pytest.fixture
def registro(monkeypatch):
    monkeypatch.setattr(algoritmos, 'ALGORITMOS', dict(algoritmos.ALGORITMOS))
    return algoritmos.ALGORITMOS


def test_nativo_que_acerta_a_cobertura_e_escolhido(rng, registro, monkeypatch):
    registro['falso'] = NativoFalso
    y = rng.normal(20, 3, 70)
    # Calibra-se a largura com a amostra, para cair perto do nominal.
    monkeypatch.setattr(NativoFalso, 'meia_largura', 5.5)

    resumo = _backtest(y, 'falso').intervalos

    assert resumo.nativo is not None
    assert resumo.motivo == CALIBRADO
    assert resumo.usar_nativo
    assert set(resumo.metodos_fold) == {intervalos.NATIVO}
    assert resumo.usada == resumo.nativo


def test_nativo_estreito_demais_cede_ao_empirico(rng, registro, monkeypatch):
    registro['falso'] = NativoFalso
    monkeypatch.setattr(NativoFalso, 'meia_largura', 0.01)

    resumo = _backtest(rng.normal(20, 3, 70), 'falso').intervalos

    assert not resumo.usar_nativo
    assert resumo.motivo == FORA_DA_FAIXA
    assert resumo.usada == resumo.empirico
    assert set(resumo.metodos_fold) == {QUANTIL}


def test_na_semanal_o_nativo_nunca_conta_como_calibrado(rng, registro):
    registro['falso'] = NativoFalso

    resumo = _backtest(
        rng.normal(20, 3, 10),
        'falso',
        gran='semanal',
        passo=1,
        treino_min=6,
    ).intervalos

    assert resumo.motivo == AMOSTRA_INSUFICIENTE
    assert set(resumo.metodos_fold) == {STUDENT}


@pytest.mark.parametrize('classe', [NativoQuebrado, NativoComErro])
def test_nativo_invalido_vira_sem_nativo(rng, registro, classe):
    registro['falso'] = classe

    resumo = _backtest(rng.normal(20, 3, 56), 'falso').intervalos

    assert resumo.nativo is None
    assert resumo.motivo == SEM_NATIVO


def test_alterar_o_teste_do_fold_nao_muda_o_ajuste_do_fold(rng):
    y = rng.poisson(2, 70).astype(float)
    alterado = y.copy()
    alterado[63:] += 100  # teste do último fold

    antes = _backtest(y, 'media_historica').folds[-1].intervalos
    depois = _backtest(alterado, 'media_historica').folds[-1].intervalos

    assert antes.calibracao == depois.calibracao
    for nivel in NIVEIS:
        assert antes.empirico[nivel][1].tolist() == (
            depois.empirico[nivel][1].tolist()
        )


def _serie_com_zeros(rng, n=56):
    # Metade de zeros e treino crescente: sem piso, o inferior fica acima de 0.
    y = rng.poisson(np.linspace(2, 12, n)).astype(float)
    y[::2] = 0
    return y


def test_piso_zero_vale_para_o_empirico_do_fold(rng):
    resultado = _backtest(_serie_com_zeros(rng), 'media_historica')

    for fold in resultado.folds:
        assert fold.intervalos.calibracao.fracao_zeros >= 0.45  # noqa: PLR2004
        for nivel in NIVEIS:
            assert (fold.intervalos.empirico[nivel][0] == 0).all()


def test_piso_zero_vale_para_o_nativo_do_fold(rng, registro, monkeypatch):
    registro['falso'] = NativoFalso
    monkeypatch.setattr(NativoFalso, 'meia_largura', 0.1)

    resultado = _backtest(_serie_com_zeros(rng), 'falso')

    for fold in resultado.folds:
        assert (fold.intervalos.nativo[0.95][0] == 0).all()


def test_piso_usa_so_o_treino_do_fold(rng):
    # Zeros só no teste do último fold não acionam o piso desse fold.
    y = rng.normal(30, 1, 56).round()
    y[49:] = 0

    ultimo = _backtest(y, 'media_historica').folds[-1].intervalos

    assert ultimo.calibracao.fracao_zeros == 0
    assert (ultimo.empirico[0.95][0] > 0).all()


def test_nativa_guarda_a_fracao_de_zeros_do_treino():
    calibracao = intervalos.nativa(NIVEIS, 3, np.array([0.0, 1.0, 2.0, 3.0]))

    assert calibracao.metodo == intervalos.NATIVO
    assert calibracao.fracao_zeros == pytest.approx(0.25)


def test_backtest_sem_config_nao_calcula_intervalos(rng):
    y = rng.poisson(2, 56).astype(float)
    particao = _particao('item A', 'diaria', 56, 42, 7)

    resultado = rodar_backtest(
        _serie(y, 'diaria'), particao, 'naive', {}, SEED
    )

    assert resultado.intervalos is None
    assert resultado.folds[0].intervalos is None


def test_cobertura_do_backtest_confere_com_a_conta_a_mao():
    # Série 0, 0, 1, 2, ..., 7, 8 e média histórica: 1 fold, 1 ponto.
    y = np.array([0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])

    resultado = _backtest(
        y, 'media_historica', gran='semanal', passo=1, treino_min=9
    )

    fold = resultado.folds[0]
    inferior, superior = fold.intervalos.empirico[0.95]
    esperado = contar(y[9:], inferior, superior)
    assert resultado.intervalos.empirico[0.95] == esperado
    assert esperado.n == 1


def test_sensibilidade_da_cobertura_tira_so_o_periodo_atipico():
    # Item C semanal: a semana 07-19 (40) fica fora do intervalo do fold 1.
    y = [10.0, 11.0, 9.0, 10.0, 11.0, 9.0, 40.0, 10.0, 9.0, 11.0]
    particao = _particao('item C', 'semanal', 10, 6, 1)

    resumo = rodar_backtest(
        _serie(y, 'semanal'), particao, 'media_historica', {}, SEED, CONFIG
    ).intervalos

    assert resumo.empirico[0.95].n == len(particao.folds)
    assert resumo.sem_atipico[0.95].n == len(particao.folds) - 1


def _casos_algoritmos():
    """Primeira combinação de cada algoritmo implementado, por granularidade.

    Lê o registro: os candidatos de #10 e #11 entram aqui sem editar o teste.
    """
    casos = {}
    for linha in tabela():
        chave = (linha['algoritmo'], linha['granularidade'])
        if linha['entra'] and linha['algoritmo'] in algoritmos.ALGORITMOS:
            primeira = {k: v[0] for k, v in linha['espaco'].items()}
            casos.setdefault(chave, primeira)
    return [(a, g, hp) for (a, g), hp in sorted(casos.items())]


CORTADOS_DA_TABELA = {'arima', 'prophet', 'ets_holt_amortecido'}


def test_registro_tem_casos_para_todo_algoritmo():
    cobertos = {a for a, _, _ in _casos_algoritmos()}

    assert cobertos == set(algoritmos.ALGORITMOS) - CORTADOS_DA_TABELA


@pytest.mark.parametrize(('nome', 'gran', 'hp'), _casos_algoritmos())
def test_todo_algoritmo_recebe_intervalos_validos(rng, nome, gran, hp):
    if gran == 'diaria':
        y = rng.poisson(1.5, 56).astype(float)
        particao = _particao('item A', gran, 56, 42, 7)
    else:
        y = rng.poisson(10, 10).astype(float)
        particao = _particao('item A', gran, 10, 6, 1)

    resultado = rodar_backtest(
        _serie(y, gran), particao, nome, hp, SEED, CONFIG
    )

    assert next(iter(resultado.intervalos.usada.values())).n > 0
    for fold in resultado.folds:
        limites = fold.intervalos.nativo or fold.intervalos.empirico
        previsto = np.asarray(fold.previsto)
        for par in (limites, fold.intervalos.empirico):
            inf80, sup80 = par[0.80]
            inf95, sup95 = par[0.95]
            definidos = np.isfinite(inf95)
            assert (inf95[definidos] >= 0).all()
            assert (inf95[definidos] <= inf80[definidos]).all()
            assert (sup95[definidos] >= sup80[definidos]).all()
            assert (inf80[definidos] <= previsto[definidos]).all()
            assert (sup80[definidos] >= previsto[definidos]).all()
