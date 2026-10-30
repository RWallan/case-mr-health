"""Confiança de um modelo a partir do MASE do backtest (#9, ADR 0008).

A confiança é metadado da versão do modelo: é calculada só com os folds do
backtest e não entra em nenhuma seleção. Insuficiente não é Ruim: significa
que não há evidência para atribuir uma faixa, porque o MASE é indefinido,
porque há folds de menos ou porque o MASE é instável.
"""

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

import mlflow
import numpy as np
from mlflow import MlflowClient
from scipy import stats

from case_mr_health.backtest import ResultadoBacktest
from case_mr_health.config import Settings

FAIXAS = ('Ótima', 'Boa', 'Média', 'Ruim')
INSUFICIENTE = 'Insuficiente'

MOTIVO_FAIXA = 'faixa'
MOTIVO_INDEFINIDO = 'mase_indefinido'
MOTIVO_POUCOS_FOLDS = 'folds_insuficientes'
MOTIVO_INSTAVEL = 'mase_instavel'

MIN_FOLDS = 2


@dataclass(frozen=True)
class Confianca:
    """Status, motivo e a evidência que os sustenta."""

    status: str
    motivo: str
    n_folds: int
    mase: float = float('nan')
    dp: float = float('nan')
    ic_inferior: float = float('nan')
    ic_superior: float = float('nan')
    faixa_pontual: str | None = None
    folds_indefinidos: tuple[int, ...] = ()

    def tags(self) -> dict[str, str]:
        """Tags `confianca*`; o que não é definido fica de fora."""
        tags = {
            'confianca': self.status,
            'confianca_motivo': self.motivo,
            'confianca_n_folds': str(self.n_folds),
        }
        for chave, valor in {
            'mase': self.mase,
            'mase_dp': self.dp,
            'ic_inferior': self.ic_inferior,
            'ic_superior': self.ic_superior,
        }.items():
            if np.isfinite(valor):
                tags[f'confianca_{chave}'] = f'{valor:.6f}'
        if self.faixa_pontual is not None:
            tags['confianca_faixa_pontual'] = self.faixa_pontual
        if self.folds_indefinidos:
            tags['confianca_folds_indefinidos'] = ','.join(
                str(f) for f in self.folds_indefinidos
            )
        return tags


def faixa(mase: float, limites: Sequence[float]) -> str:
    """Faixa do MASE; o limite superior de cada faixa é inclusivo."""
    return FAIXAS[indice_faixa(mase, limites)]


def intervalo(
    mases: Sequence[float], nivel: float
) -> tuple[float, float, float, float]:
    """Média, desvio-padrão e IC t da média, com o inferior truncado em 0.

    A cobertura é nominal: os folds compartilham treino e a série é
    autocorrelacionada. O IC serve de régua para o critério de instabilidade.
    """
    valores = np.asarray(mases, dtype=float)
    media = float(valores.mean())
    dp = float(valores.std(ddof=1))
    n = len(valores)
    meia = stats.t.ppf((1 + nivel) / 2, n - 1) * dp / np.sqrt(n)
    return media, dp, max(media - float(meia), 0.0), media + float(meia)


def avaliar(mases: Sequence[float], cfg: Settings) -> Confianca:
    """Confiança a partir do MASE de cada fold do backtest."""
    n = len(mases)
    indefinidos = tuple(
        i for i, m in enumerate(mases, start=1) if not np.isfinite(m)
    )
    if indefinidos:
        return Confianca(
            INSUFICIENTE, MOTIVO_INDEFINIDO, n, folds_indefinidos=indefinidos
        )
    if n < MIN_FOLDS:
        return Confianca(
            INSUFICIENTE,
            MOTIVO_POUCOS_FOLDS,
            n,
            mase=float(np.mean(mases)) if n else float('nan'),
        )
    limites = cfg.confianca_limites
    media, dp, inferior, superior = intervalo(mases, cfg.confianca_nivel_ic)
    pontual = faixa(media, limites)
    fronteiras = indice_faixa(superior, limites)
    fronteiras -= indice_faixa(inferior, limites)
    instavel = fronteiras > cfg.confianca_max_fronteiras_ic
    return Confianca(
        INSUFICIENTE if instavel else pontual,
        MOTIVO_INSTAVEL if instavel else MOTIVO_FAIXA,
        n,
        media,
        dp,
        inferior,
        superior,
        pontual,
    )


def registrar(
    nome: str, versao: str, resultado: ResultadoBacktest, cfg: Settings
) -> Confianca:
    """Grava a confiança na versão do modelo e no run ativo."""
    confianca = avaliar([r.metricas['mase'] for r in resultado.folds], cfg)
    tags = confianca.tags()
    mlflow.set_tags(tags)
    cliente = MlflowClient()
    for chave, valor in tags.items():
        cliente.set_model_version_tag(nome, versao, chave, valor)
    return confianca


def indice_faixa(mase: float, limites: Sequence[float]) -> int:
    return bisect_left(limites, mase)
