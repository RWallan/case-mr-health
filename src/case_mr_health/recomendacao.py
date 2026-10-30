"""Regra determinística de recomendação (#18, ADR 0004).

Compara a demanda média prevista para as 2 próximas semanas com a venda
média das 4 últimas e a confronta com o Q3 das variações históricas de
janelas deslizantes com o mesmo formato. Nenhum modelo de linguagem decide
nada; a confiança do modelo não entra (D-020).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

SEMANAS_BASE = 4
SEMANAS_PREVISTAS = 2
MINIMO_VARIACOES = 3

Resultado = Literal[
    'aumento_significativo', 'reducao_significativa', 'estavel', 'insuficiente'
]
Motivo = Literal['sem_venda_recente', 'variacoes_insuficientes']


@dataclass(frozen=True)
class Recomendacao:
    resultado: Resultado
    motivo: Motivo | None
    variacao: float | None
    limite_aplicado: float | None
    media_vendida_4s: float
    media_prevista_2s: float
    n_variacoes_positivas: int
    n_variacoes_negativas: int


def variacoes_historicas(vendas: Sequence[float]) -> list[float]:
    """Variação de cada janela: 2 semanas reais contra as 4 anteriores.

    A janela com base zero é descartada.
    """
    tamanho = SEMANAS_BASE + SEMANAS_PREVISTAS
    variacoes = []
    for inicio in range(len(vendas) - tamanho + 1):
        base = float(np.mean(vendas[inicio : inicio + SEMANAS_BASE]))
        if base == 0:
            continue
        seguintes = vendas[inicio + SEMANAS_BASE : inicio + tamanho]
        variacoes.append(float(np.mean(seguintes)) / base - 1)
    return variacoes


def recomendar(
    vendas: Sequence[float], previsao: Sequence[float]
) -> Recomendacao:
    """`vendas`: semanas completas até a origem; `previsao`: 2 semanas."""
    if len(previsao) != SEMANAS_PREVISTAS:
        raise ValueError(
            f'a recomendação usa {SEMANAS_PREVISTAS} semanas previstas, '
            f'recebeu {len(previsao)}'
        )
    if len(vendas) < SEMANAS_BASE:
        raise ValueError(
            f'a recomendação exige {SEMANAS_BASE} semanas de venda, '
            f'recebeu {len(vendas)}'
        )
    base = float(np.mean(vendas[-SEMANAS_BASE:]))
    prevista = float(np.mean(previsao))
    historicas = variacoes_historicas(vendas)
    positivas = [v for v in historicas if v > 0]
    negativas = [-v for v in historicas if v < 0]
    contagens = {
        'media_vendida_4s': base,
        'media_prevista_2s': prevista,
        'n_variacoes_positivas': len(positivas),
        'n_variacoes_negativas': len(negativas),
    }
    if base == 0:
        return Recomendacao(
            'insuficiente', 'sem_venda_recente', None, None, **contagens
        )
    variacao = prevista / base - 1
    if variacao == 0:
        return Recomendacao('estavel', None, 0.0, None, **contagens)
    do_lado = positivas if variacao > 0 else negativas
    if len(do_lado) < MINIMO_VARIACOES:
        return Recomendacao(
            'insuficiente',
            'variacoes_insuficientes',
            variacao,
            None,
            **contagens,
        )
    limite = float(np.percentile(do_lado, 75))
    if abs(variacao) <= limite:
        resultado = 'estavel'
    elif variacao > 0:
        resultado = 'aumento_significativo'
    else:
        resultado = 'reducao_significativa'
    return Recomendacao(resultado, None, variacao, limite, **contagens)
