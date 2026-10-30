"""Candidatos ETS, ARIMA e SARIMA via `statsmodels` (#11).

Os nomes e os hiperparâmetros vêm de `candidatos.py` (D-004). Valores
simbólicos da tabela são mapeados aqui, e valor desconhecido é rejeitado em
vez de ignorado.

Cada `ajustar` verifica a convergência e as premissas com o treino que
recebeu e publica um `DiagnosticoAjuste` para quem estiver coletando
(`coletar_diagnosticos`). Modelo que não converge levanta
`FalhaConvergencia`, inclusive quando a biblioteca só emite um aviso: a
regra de registro está em `treino.py` (ADR 0010).
"""

import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import ClassVar, Self

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

from case_mr_health import diagnosticos
from case_mr_health.algoritmos import _validar, registrar
from case_mr_health.candidatos import (
    ATENDIDA,
    INCONCLUSIVA,
    NAO_ATENDIDA,
    NAO_TESTAVEL,
)

MAX_ITERACOES = 1000
ALFA_TESTES = 0.05
MIN_OBS_LJUNG_BOX = diagnosticos.MIN_OBS_ESTACIONARIEDADE
LAGS_NAO_SAZONAL = 10
FRACAO_LAGS = 5  # no máximo n/5 lags no Ljung-Box
MIN_CICLOS_SAZONALIDADE = 5  # 5 observações por grupo no Kruskal-Wallis
RAIZ_PROXIMA_DA_UNIDADE = 1.01
OBSERVACOES_POR_PARAMETRO = 2  # 6 pontos, até 3 parâmetros (D-004)

ALFA_ESTIMADO = 'estimado'
SEM_TENDENCIA = 'nenhuma'
LIMITES_PHI = {'estimado em [0,8; 0,98]': (0.8, 0.98)}

ERROS_DE_AJUSTE = (
    np.linalg.LinAlgError,
    ValueError,
    RuntimeError,
    FloatingPointError,
    OverflowError,
)


class FalhaConvergencia(Exception):
    """O modelo não pôde ser estimado com o treino recebido."""

    def __init__(
        self, algoritmo: str, hiperparametros: dict, n_treino: int, motivo: str
    ):
        super().__init__(f'{algoritmo} (n = {n_treino}): {motivo}')
        self.algoritmo = algoritmo
        self.hiperparametros = hiperparametros
        self.n_treino = n_treino
        self.motivo = motivo


@dataclass(frozen=True)
class VerificacaoPremissa:
    """Resultado de uma premissa; `detalhe` guarda o que a sustenta."""

    premissa: str
    situacao: str
    detalhe: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DiagnosticoAjuste:
    """O que aconteceu em uma chamada de `ajustar`."""

    algoritmo: str
    n_treino: int
    convergiu: bool
    avisos: tuple[str, ...] = ()
    premissas: tuple[VerificacaoPremissa, ...] = ()


_COLETOR: ContextVar[list[DiagnosticoAjuste] | None] = ContextVar(
    'coletor_diagnosticos', default=None
)


@contextmanager
def coletar_diagnosticos() -> Iterator[list[DiagnosticoAjuste]]:
    """Reúne os diagnósticos dos ajustes feitos dentro do bloco.

    O contrato `ajustar(y)` não devolve diagnóstico e o backtest não guarda
    os previsores dos folds; assim, ambos seguem sem saber deste registro.
    """
    coletados: list[DiagnosticoAjuste] = []
    token = _COLETOR.set(coletados)
    try:
        yield coletados
    finally:
        _COLETOR.reset(token)


def publicar_diagnostico(diagnostico: DiagnosticoAjuste) -> None:
    coletados = _COLETOR.get()
    if coletados is not None:
        coletados.append(diagnostico)


def verificar_estacionariedade(y: np.ndarray, d: int = 0):
    """ADF e KPSS (`diagnosticos`) na série após `d` diferenças."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # p do KPSS truncado pela tabela
        teste = diagnosticos.estacionariedade(np.diff(y, n=d))
    if not teste['testavel']:
        return VerificacaoPremissa(
            'estacionariedade', NAO_TESTAVEL, {'n': teste['n'], 'd': d}
        )
    situacao = {
        'estacionária': ATENDIDA,
        'raiz unitária / não estacionária': NAO_ATENDIDA,
    }.get(teste['veredito'], INCONCLUSIVA)
    return VerificacaoPremissa(
        'estacionariedade',
        situacao,
        {
            'n': teste['n'],
            'd': d,
            'adf_p': teste['adf_p'],
            'kpss_p': teste['kpss_p'],
        },
    )


def _ljung_box_p(
    serie: np.ndarray, periodo: int, parametros: int
) -> tuple[float | None, int]:
    """Valor-p do Ljung-Box, ou `None` se não é testável, e o lag usado."""
    n = len(serie)
    desejado = 2 * periodo if periodo > 1 else LAGS_NAO_SAZONAL
    lag = min(desejado, n // FRACAO_LAGS)
    if n < MIN_OBS_LJUNG_BOX or lag <= parametros or np.ptp(serie) == 0:
        return None, lag
    teste = acorr_ljungbox(serie, lags=[lag], model_df=parametros)
    return float(teste['lb_pvalue'].iloc[0]), lag


def verificar_residuos(residuos: np.ndarray, periodo: int, parametros: int):
    """Resíduos sem autocorrelação; não rejeitar não prova ruído branco."""
    p, lag = _ljung_box_p(residuos, periodo, parametros)
    if p is None:
        return VerificacaoPremissa(
            'residuos_sem_autocorrelacao',
            NAO_TESTAVEL,
            {'n': len(residuos), 'lag': lag},
        )
    return VerificacaoPremissa(
        'residuos_sem_autocorrelacao',
        ATENDIDA if p >= ALFA_TESTES else NAO_ATENDIDA,
        {'n': len(residuos), 'lag': lag, 'ljung_box_p': p},
    )


def verificar_dependencia(y: np.ndarray, periodo: int, d: int = 0):
    """Há dependência a modelar? Não rejeitar ruído é inconclusivo."""
    serie = np.diff(y, n=d)
    p, lag = _ljung_box_p(serie, periodo, 0)
    if p is None:
        return VerificacaoPremissa(
            'dependencia_temporal',
            NAO_TESTAVEL,
            {'n': len(serie), 'lag': lag},
        )
    return VerificacaoPremissa(
        'dependencia_temporal',
        ATENDIDA if p < ALFA_TESTES else INCONCLUSIVA,
        {'n': len(serie), 'lag': lag, 'ljung_box_p': p},
    )


def verificar_sazonalidade(y: np.ndarray, periodo: int):
    """Kruskal-Wallis entre posições do ciclo, com ciclos completos.

    Usa só a posição no ciclo, então não depende do rótulo do dia da
    semana. Não rejeitar é inconclusivo (poder baixo), não reprovação.
    """
    ciclos = len(y) // periodo
    if ciclos < MIN_CICLOS_SAZONALIDADE or np.ptp(y) == 0:
        return VerificacaoPremissa(
            'sazonalidade', NAO_TESTAVEL, {'ciclos': ciclos}
        )
    por_posicao = y[-ciclos * periodo :].reshape(ciclos, periodo).T
    p = float(stats.kruskal(*por_posicao).pvalue)
    return VerificacaoPremissa(
        'sazonalidade',
        ATENDIDA if p < ALFA_TESTES else INCONCLUSIVA,
        {'ciclos': ciclos, 'kruskal_p': p},
    )


def verificar_zeros(y: np.ndarray):
    """Erro contínuo e simétrico; zeros violam em parte (tabela do #6)."""
    fracao = float((y == 0).mean())
    return VerificacaoPremissa(
        'valores_continuos',
        NAO_ATENDIDA if fracao > 0 else INCONCLUSIVA,
        {'fracao_zeros': fracao},
    )


def verificar_parametros(n: int, parametros: int):
    """Mesma razão do ARIMA semanal: 6 pontos, até 3 parâmetros."""
    return VerificacaoPremissa(
        'parametros_por_observacao',
        ATENDIDA
        if parametros * OBSERVACOES_POR_PARAMETRO <= n
        else NAO_ATENDIDA,
        {'n': n, 'parametros': parametros},
    )


def verificar_raizes(raizes_ar: np.ndarray, raizes_ma: np.ndarray):
    """Raízes estimadas longe do círculo unitário (testável com qualquer n)."""
    raizes = np.abs(np.concatenate([raizes_ar, raizes_ma]))
    if raizes.size == 0:
        return VerificacaoPremissa('raizes_fora_do_circulo', NAO_TESTAVEL)
    menor = float(raizes.min())
    return VerificacaoPremissa(
        'raizes_fora_do_circulo',
        ATENDIDA if menor >= RAIZ_PROXIMA_DA_UNIDADE else NAO_ATENDIDA,
        {'menor_modulo': menor},
    )


def ajustar_monitorado(
    algoritmo: str,
    hiperparametros: dict,
    n_treino: int,
    estimar: Callable[[], object],
    convergiu: Callable[[object], bool],
) -> tuple[object, tuple[str, ...]]:
    """Roda `estimar`, transformando erro ou aviso de convergência em falha."""

    def falhar(motivo: str, avisos: tuple[str, ...] = ()):
        publicar_diagnostico(
            DiagnosticoAjuste(algoritmo, n_treino, False, (motivo, *avisos))
        )
        return FalhaConvergencia(algoritmo, hiperparametros, n_treino, motivo)

    with warnings.catch_warnings(record=True) as capturados:
        warnings.simplefilter('always')
        try:
            resultado = estimar()
        except ERROS_DE_AJUSTE as erro:
            raise falhar(f'{type(erro).__name__}: {erro}') from erro
    avisos = tuple(
        sorted({
            f'{a.category.__name__}: {a.message}'
            for a in capturados
            if not issubclass(a.category, (DeprecationWarning, FutureWarning))
        })
    )
    if any(issubclass(a.category, ConvergenceWarning) for a in capturados):
        raise falhar('aviso de convergência do otimizador', avisos)
    if not convergiu(resultado):
        raise falhar('otimizador não convergiu', avisos)
    return resultado, avisos


def _convergiu(resultado) -> bool:
    retorno = resultado.mle_retvals
    return bool(retorno.get('converged', True)) and bool(
        np.isfinite(resultado.params).all()
    )


class _PrevisorStatsmodels:
    """Ajuste monitorado e intervalos comuns aos modelos da biblioteca."""

    algoritmo: ClassVar[str]
    dependencias: ClassVar[tuple[str, ...]] = (
        'numpy',
        'pandas',
        'scipy',
        'statsmodels',
    )

    def ajustar(self, y) -> Self:
        y = _validar(y)
        self._n = len(y)
        self._resultado, avisos = ajustar_monitorado(
            self.algoritmo,
            self._hiperparametros(),
            len(y),
            lambda: self._estimar(y),
            _convergiu,
        )
        self.diagnostico = DiagnosticoAjuste(
            self.algoritmo,
            len(y),
            True,
            avisos,
            self._premissas(y, self._resultado),
        )
        publicar_diagnostico(self.diagnostico)
        return self

    def intervalos_nativos(
        self, horizonte: int, niveis: tuple[float, ...]
    ) -> dict[float, tuple[np.ndarray, np.ndarray]]:
        """Por nível: (inferior, superior), sem truncar."""
        return {nivel: self._limites(horizonte, 1 - nivel) for nivel in niveis}


class _Ets(_PrevisorStatsmodels):
    """ETS de erro aditivo com estados iniciais estimados.

    Recebe `pd.Series`: em `statsmodels` 0.15.0, `get_prediction` quebra
    com `ndarray` (`PredictionResults` lê `predicted_mean.index`).
    """

    tendencia: ClassVar[str | None] = None
    amortecido: ClassVar[bool] = False

    def __init__(
        self,
        periodo_sazonal: int | None = None,
        limites_phi: tuple[float, float] | None = None,
    ):
        self.periodo_sazonal = periodo_sazonal
        self.limites_phi = limites_phi

    def _estimar(self, y):
        modelo = ETSModel(
            pd.Series(y),
            error='add',
            trend=self.tendencia,
            damped_trend=self.amortecido,
            seasonal='add' if self.periodo_sazonal else None,
            seasonal_periods=self.periodo_sazonal,
            initialization_method='estimated',
            bounds=(
                {'damping_trend': self.limites_phi}
                if self.limites_phi
                else None
            ),
        )
        return modelo.fit(disp=False, maxiter=MAX_ITERACOES)

    def prever(self, horizonte):
        return self._resultado.forecast(horizonte).to_numpy(dtype=float)

    def _limites(self, horizonte, alfa):
        predicao = self._resultado.get_prediction(
            start=self._n, end=self._n + horizonte - 1
        )
        limites = predicao.pred_int(alpha=alfa).to_numpy(dtype=float)
        return limites[:, 0], limites[:, 1]

    def _premissas(self, y, resultado):
        periodo = self.periodo_sazonal or 1
        # A variância do erro conta como parâmetro, como no ARIMA.
        parametros = len(resultado.params) + 1
        premissas = [
            verificar_parametros(len(y), parametros),
            verificar_zeros(y),
            verificar_residuos(
                np.asarray(resultado.resid, dtype=float),
                periodo,
                len(resultado.params),
            ),
        ]
        if not self.amortecido:
            premissas.append(verificar_estacionariedade(y))
        if self.periodo_sazonal:
            premissas.append(verificar_sazonalidade(y, self.periodo_sazonal))
        return tuple(premissas)


@registrar('ets_ses')
class EtsSes(_Ets):
    """ANN: suavização exponencial simples."""

    algoritmo = 'ets_ses'

    def __init__(self, alfa: str):
        if alfa != ALFA_ESTIMADO:
            raise ValueError(f'alfa sem mapeamento: {alfa}')
        super().__init__()
        self.alfa = alfa

    def _hiperparametros(self):
        return {'alfa': self.alfa}


@registrar('ets_holt_winters_aditivo')
class EtsHoltWintersAditivo(_Ets):
    """ANA: nível e sazonalidade aditivos, sem tendência."""

    algoritmo = 'ets_holt_winters_aditivo'

    def __init__(self, periodo: int, tendencia: str):
        if tendencia != SEM_TENDENCIA:
            raise ValueError(f'tendência sem mapeamento: {tendencia}')
        super().__init__(periodo_sazonal=int(periodo))
        self.periodo = int(periodo)
        self.tendencia_tabela = tendencia

    def _hiperparametros(self):
        return {'periodo': self.periodo, 'tendencia': self.tendencia_tabela}


@registrar('ets_holt_amortecido')
class EtsHoltAmortecido(_Ets):
    """AAdN: tendência amortecida, com φ estimado nos limites da tabela."""

    algoritmo = 'ets_holt_amortecido'
    tendencia = 'add'
    amortecido = True

    def __init__(self, phi: str):
        if phi not in LIMITES_PHI:
            raise ValueError(f'phi sem mapeamento: {phi}')
        super().__init__(limites_phi=LIMITES_PHI[phi])
        self.phi = phi

    def _hiperparametros(self):
        return {'phi': self.phi}


class _Arima(_PrevisorStatsmodels):
    """(S)ARIMA por máxima verossimilhança em espaço de estados.

    A constante segue a tabela: há constante quando não há diferenciação.
    """

    def __init__(
        self,
        ordem: tuple[int, int, int],
        ordem_sazonal: tuple[int, int, int, int] = (0, 0, 0, 0),
    ):
        self.ordem = tuple(int(v) for v in ordem)
        self.ordem_sazonal = tuple(int(v) for v in ordem_sazonal)

    @property
    def diferencas(self) -> int:
        return self.ordem[1] + self.ordem_sazonal[1]

    @property
    def tendencia(self) -> str:
        return 'n' if self.diferencas else 'c'

    def _estimar(self, y):
        modelo = ARIMA(
            y,
            order=self.ordem,
            seasonal_order=self.ordem_sazonal,
            trend=self.tendencia,
        )
        return modelo.fit(
            method_kwargs={'maxiter': MAX_ITERACOES}, cov_type='none'
        )

    def prever(self, horizonte):
        previsao = self._resultado.get_forecast(horizonte)
        return np.asarray(previsao.predicted_mean, dtype=float)

    def _limites(self, horizonte, alfa):
        limites = self._resultado.get_forecast(horizonte).conf_int(alpha=alfa)
        limites = np.asarray(limites, dtype=float)
        return limites[:, 0], limites[:, 1]

    def _premissas(self, y, resultado):
        d = self.diferencas
        periodo = self.ordem_sazonal[3] or 1
        arma = sum(self.ordem[::2]) + sum(self.ordem_sazonal[::2])
        return (
            verificar_parametros(len(y), len(resultado.params)),
            verificar_estacionariedade(y, d),
            verificar_dependencia(y, periodo, d),
            verificar_raizes(resultado.arroots, resultado.maroots),
            verificar_residuos(
                np.asarray(resultado.resid, dtype=float)[d:], periodo, arma
            ),
        )

    def _hiperparametros(self):
        return {'ordem': self.ordem, 'ordem_sazonal': self.ordem_sazonal}


@registrar('arima')
class Arima(_Arima):
    algoritmo = 'arima'

    def __init__(self, ordem: tuple[int, int, int]):
        super().__init__(ordem)

    def _hiperparametros(self):
        return {'ordem': self.ordem}


@registrar('sarima')
class Sarima(_Arima):
    algoritmo = 'sarima'

    def __init__(
        self,
        ordem: tuple[int, int, int],
        ordem_sazonal: tuple[int, int, int, int],
    ):
        super().__init__(ordem, ordem_sazonal)

    def _premissas(self, y, resultado):
        return (
            *super()._premissas(y, resultado),
            verificar_sazonalidade(y, self.ordem_sazonal[3]),
        )
