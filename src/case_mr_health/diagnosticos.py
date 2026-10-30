"""Diagnósticos de séries curtas e intermitentes usados na EDA (#5)."""

from dataclasses import dataclass

import numpy as np
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.proportion import proportion_confint
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf

# Limiares de Syntetos, Boylan e Croston (2005) para a classificação.
LIMIAR_ADI = 1.32
LIMIAR_CV2 = 0.49
MIN_OBS_ESTACIONARIEDADE = 30


@dataclass(frozen=True)
class Intermitencia:
    adi: float
    cv2: float
    classe: str


def proporcao_zeros(y: np.ndarray) -> tuple[float, float, float]:
    """Proporção de zeros e IC de 95% de Wilson."""
    zeros = int((np.asarray(y) == 0).sum())
    baixo, alto = proporcao_wilson(zeros, len(y))
    return zeros / len(y), baixo, alto


def proporcao_wilson(sucessos: int, n: int) -> tuple[float, float]:
    baixo, alto = proportion_confint(sucessos, n, alpha=0.05, method='wilson')
    return float(baixo), float(alto)


def intermitencia(y: np.ndarray) -> Intermitencia:
    """ADI e CV² (variância relativa dos tamanhos não nulos).

    ADI = períodos / períodos com demanda; CV² usa desvio-padrão
    populacional (ddof=0) dos tamanhos não nulos.
    """
    y = np.asarray(y, dtype=float)
    nao_nulos = y[y > 0]
    if len(nao_nulos) == 0:
        return Intermitencia(np.inf, np.nan, 'sem demanda')
    adi = len(y) / len(nao_nulos)
    cv2 = float((nao_nulos.std() / nao_nulos.mean()) ** 2)
    if adi < LIMIAR_ADI:
        classe = 'suave' if cv2 < LIMIAR_CV2 else 'errática'
    else:
        classe = 'intermitente' if cv2 < LIMIAR_CV2 else 'irregular'
    return Intermitencia(float(adi), cv2, classe)


def bootstrap_blocos(
    matriz: np.ndarray, estatistica, n_boot: int = 10_000, seed: int = 0
) -> tuple[float, float, float]:
    """IC de 95% por bootstrap percentil, reamostrando linhas (semanas).

    `matriz` tem uma linha por bloco (semana) e uma coluna por dia/série.
    """
    rng = np.random.default_rng(seed)
    n = len(matriz)
    valores = np.array([
        estatistica(matriz[rng.integers(0, n, n)]) for _ in range(n_boot)
    ])
    valores = valores[np.isfinite(valores)]
    return (
        float(estatistica(matriz)),
        float(np.percentile(valores, 2.5)),
        float(np.percentile(valores, 97.5)),
    )


def razao_fim_de_semana(semanas_x_dias: np.ndarray) -> float:
    """Média diária de sexta a domingo sobre a de segunda a quinta.

    Colunas na ordem segunda..domingo; cada linha é uma semana completa.
    """
    seg_qui = semanas_x_dias[:, :4].mean()
    sex_dom = semanas_x_dias[:, 4:].mean()
    return float(sex_dom / seg_qui) if seg_qui > 0 else np.nan


def sazonalidade_semanal(
    semanas_x_dias: np.ndarray, n_perm: int = 10_000, seed: int = 0
) -> dict:
    """Kruskal-Wallis (dias agrupados), Friedman (semanas como blocos) e
    permutação do dia da semana dentro de cada semana (estatística F).
    """
    m = np.asarray(semanas_x_dias, dtype=float)
    kw = stats.kruskal(*m.T)
    if np.ptp(m, axis=1).min() == 0:
        friedman_p = np.nan  # semana sem variação: Friedman degenerado
    else:
        friedman_p = stats.friedmanchisquare(*m.T).pvalue

    def f_dia(mat):
        return stats.f_oneway(*mat.T).statistic

    rng = np.random.default_rng(seed)
    observado = f_dia(m)
    maiores = sum(
        f_dia(np.array([rng.permutation(linha) for linha in m])) >= observado
        for _ in range(n_perm)
    )
    return {
        'kruskal_p': float(kw.pvalue),
        'friedman_p': float(friedman_p),
        'permutacao_p': (maiores + 1) / (n_perm + 1),
    }


def autocorrelacao(y: np.ndarray, nlags: int, lags_lb: list[int]) -> dict:
    """ACF/PACF e Ljung-Box; faixa de Bartlett aproximada ±1,96/√n."""
    y = np.asarray(y, dtype=float)
    lb = acorr_ljungbox(y, lags=lags_lb)
    return {
        'acf': acf(y, nlags=nlags),
        'pacf': pacf(y, nlags=min(nlags, len(y) // 2 - 1)),
        'banda': 1.96 / np.sqrt(len(y)),
        'ljung_box_p': dict(zip(lags_lb, lb['lb_pvalue'], strict=True)),
    }


def estacionariedade(y: np.ndarray) -> dict:
    """ADF (H0: raiz unitária) e KPSS (H0: estacionária em nível)."""
    y = np.asarray(y, dtype=float)
    if len(y) < MIN_OBS_ESTACIONARIEDADE or np.ptp(y) == 0:
        return {'testavel': False, 'n': len(y)}
    adf_p = adfuller(y, regression='c', autolag='AIC')[1]
    kpss_p = kpss(y, regression='c', nlags='auto')[1]
    if adf_p < 0.05 <= kpss_p:  # noqa: PLR2004
        veredito = 'estacionária'
    elif kpss_p < 0.05 <= adf_p:  # noqa: PLR2004
        veredito = 'raiz unitária / não estacionária'
    else:
        veredito = 'inconclusivo'
    return {
        'testavel': True,
        'n': len(y),
        'adf_p': float(adf_p),
        'kpss_p': float(kpss_p),
        'veredito': veredito,
    }


def sinalizar_outliers(y: np.ndarray) -> dict:
    """Sinaliza valores não nulos por MAD (|z robusto| > 3,5) e IQR."""
    y = np.asarray(y, dtype=float)
    nn = y[y > 0]
    if len(nn) == 0:
        return {'mad': [], 'iqr': []}
    mediana = np.median(nn)
    mad = np.median(np.abs(nn - mediana))
    z = 0.6745 * (y - mediana) / mad if mad > 0 else np.zeros_like(y)
    q1, q3 = np.percentile(nn, [25, 75])
    return {
        'mad': np.flatnonzero((y > 0) & (np.abs(z) > 3.5)).tolist(),  # noqa: PLR2004
        'iqr': np.flatnonzero(
            (y > 0) & ((y < q1 - 1.5 * (q3 - q1)) | (y > q3 + 1.5 * (q3 - q1)))
        ).tolist(),
    }
