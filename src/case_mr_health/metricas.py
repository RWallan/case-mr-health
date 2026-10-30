"""Métricas de erro de previsão (#7).

Todas recebem o observado e o previsto de um fold. Quando a métrica não é
definida (denominador zero), devolvem `nan`: o chamador decide o que fazer,
e o #9 trata a escala zero do MASE como Insuficiente.
"""

import numpy as np

METRICAS = ('mae', 'mse', 'rmse', 'wape', 'mase')


def mae(observado, previsto) -> float:
    return float(np.mean(np.abs(_erro(observado, previsto))))


def mse(observado, previsto) -> float:
    return float(np.mean(_erro(observado, previsto) ** 2))


def rmse(observado, previsto) -> float:
    return float(np.sqrt(mse(observado, previsto)))


def wape(observado, previsto) -> float:
    """Soma dos erros absolutos dividida pela soma do observado."""
    total = float(np.sum(np.abs(np.asarray(observado, dtype=float))))
    if total == 0:
        return float('nan')
    return float(np.sum(np.abs(_erro(observado, previsto))) / total)


def escala_mase(treino) -> float:
    """MAE do naive de um passo dentro do treino (Hyndman e Koehler, 2006)."""
    treino = np.asarray(treino, dtype=float)
    if len(treino) < 2:  # noqa: PLR2004
        return float('nan')
    return float(np.mean(np.abs(np.diff(treino))))


def mase(observado, previsto, treino) -> float:
    """MAE do fold dividido pela escala do treino; `nan` se a escala é 0."""
    return _mase(observado, previsto, escala_mase(treino))


def calcular(observado, previsto, treino) -> dict[str, float]:
    """As cinco métricas do ADR 0002 para um fold."""
    return calcular_com_escala(observado, previsto, escala_mase(treino))


def calcular_com_escala(observado, previsto, escala) -> dict[str, float]:
    """Como `calcular`, com a escala do MASE já conhecida."""
    return {
        'mae': mae(observado, previsto),
        'mse': mse(observado, previsto),
        'rmse': rmse(observado, previsto),
        'wape': wape(observado, previsto),
        'mase': _mase(observado, previsto, escala),
    }


def _mase(observado, previsto, escala) -> float:
    if not escala > 0:
        return float('nan')
    return mae(observado, previsto) / escala


def _erro(observado, previsto) -> np.ndarray:
    observado = np.asarray(observado, dtype=float)
    previsto = np.asarray(previsto, dtype=float)
    if observado.shape != previsto.shape or observado.size == 0:
        raise ValueError('observado e previsto devem ter o mesmo tamanho > 0')
    return observado - previsto
