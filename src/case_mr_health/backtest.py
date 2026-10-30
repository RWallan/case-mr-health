"""Backtest de origem móvel com janela expansiva (ADR 0002).

Recebe só a visão de desenvolvimento: a série já chega sem o OOT. Cada
fold ajusta o previsor apenas com o treino do fold, prevê o horizonte do
teste e trunca a previsão em zero.
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from case_mr_health import metricas
from case_mr_health.algoritmos import criar
from case_mr_health.particoes import Particao

# Períodos de teste mantidos na série por decisão do usuário (registro da
# Fase 1, decisão 24): o backtest relata a sensibilidade a eles.
PERIODOS_ATIPICOS: dict[tuple[str, str], date] = {
    ('item C', 'semanal'): date(2021, 7, 19),
}
FOLDS_INICIAIS_EXCLUIDOS = 2


@dataclass(frozen=True)
class ResultadoFold:
    fold: int
    treino_n: int
    teste_inicio: date
    teste_fim: date
    observado: tuple[float, ...]
    previsto: tuple[float, ...]
    escala_mase: float
    metricas: dict[str, float]


@dataclass(frozen=True)
class ResultadoBacktest:
    folds: tuple[ResultadoFold, ...]
    medias: dict[str, float]
    sensibilidade: dict[str, dict[str, float]] = field(default_factory=dict)


def media_dos_folds(folds: list[dict[str, float]]) -> dict[str, float]:
    """Média simples entre folds; `nan` se a métrica falta em algum."""
    if not folds:
        return {m: float('nan') for m in metricas.METRICAS}
    return {
        m: float(np.mean([f[m] for f in folds])) for m in metricas.METRICAS
    }


def rodar_backtest(
    serie: pd.Series,
    particao: Particao,
    algoritmo: str,
    hiperparametros: dict,
    seed: int,
) -> ResultadoBacktest:
    """Executa todos os folds da partição para um previsor da tabela."""
    if not particao.folds:
        raise ValueError(f'{particao.sku}/{particao.granularidade} sem folds')
    indice = pd.DatetimeIndex(serie.index).normalize()
    valores = serie.to_numpy(dtype=float)
    resultados = []
    for i, fold in enumerate(particao.folds, start=1):
        treino = valores[
            (indice >= pd.Timestamp(fold.treino_inicio))
            & (indice <= pd.Timestamp(fold.treino_fim))
        ]
        mascara = (indice >= pd.Timestamp(fold.teste_inicio)) & (
            indice <= pd.Timestamp(fold.teste_fim)
        )
        teste = valores[mascara]
        previsor = criar(algoritmo, hiperparametros, seed)
        previsto = np.clip(
            previsor.ajustar(treino).prever(len(teste)), 0, None
        )
        resultados.append(
            ResultadoFold(
                fold=i,
                treino_n=len(treino),
                teste_inicio=fold.teste_inicio,
                teste_fim=fold.teste_fim,
                observado=tuple(teste),
                previsto=tuple(previsto),
                escala_mase=metricas.escala_mase(treino),
                metricas=metricas.calcular(teste, previsto, treino),
            )
        )
    return ResultadoBacktest(
        folds=tuple(resultados),
        medias=media_dos_folds([r.metricas for r in resultados]),
        sensibilidade=sensibilidade(
            resultados,
            PERIODOS_ATIPICOS.get((particao.sku, particao.granularidade)),
            indice_periodos=_periodos_teste(particao, indice),
        ),
    )


def _periodos_teste(particao: Particao, indice) -> list[list[pd.Timestamp]]:
    return [
        [
            d
            for d in indice
            if pd.Timestamp(f.teste_inicio) <= d <= pd.Timestamp(f.teste_fim)
        ]
        for f in particao.folds
    ]


def sensibilidade(
    resultados: list[ResultadoFold],
    atipico: date | None,
    indice_periodos: list[list[pd.Timestamp]],
) -> dict[str, dict[str, float]]:
    """Médias dos folds sem o período atípico e sem os primeiros folds.

    Só existe para séries com período atípico declarado. Sem o período, o
    ponto sai das métricas do fold (a série e o treino não mudam); um fold
    que fica sem pontos é descartado.
    """
    if atipico is None:
        return {}
    sem_periodo = []
    for r, periodos in zip(resultados, indice_periodos, strict=True):
        manter = [p.date() != atipico for p in periodos]
        if not any(manter):
            continue
        obs = np.asarray(r.observado)[manter]
        prev = np.asarray(r.previsto)[manter]
        sem_periodo.append(
            metricas.calcular_com_escala(obs, prev, r.escala_mase)
        )
    sem_folds = [r.metricas for r in resultados[FOLDS_INICIAIS_EXCLUIDOS:]]
    return {
        'sem_periodo_atipico': media_dos_folds(sem_periodo),
        'sem_folds_1_2': media_dos_folds(sem_folds),
    }
