"""Previsores treináveis e o registro que os liga à tabela do #6.

O fluxo de treino (`backtest`, `treino`) só conhece o contrato `Previsor`
e o dicionário `ALGORITMOS`. Plugar um candidato novo (#10, #11) é escrever
uma classe com `ajustar`/`prever` e registrá-la com `@registrar('nome')`,
onde `nome` é o `algoritmo` de `candidatos.py`; as chaves do espaço de
hiperparâmetros da tabela são os argumentos do construtor.
"""

from collections.abc import Callable
from typing import Protocol, Self

import numpy as np


class Previsor(Protocol):
    """Contrato de um modelo de uma única série."""

    def ajustar(self, y: np.ndarray) -> Self:
        """Ajusta apenas com `y` (o treino do fold, em ordem cronológica)."""

    def prever(self, horizonte: int) -> np.ndarray:
        """Previsão dos próximos `horizonte` períodos (sem truncar)."""


ALGORITMOS: dict[str, Callable[..., Previsor]] = {}


def registrar(nome: str):
    def decorador(fabrica):
        if nome in ALGORITMOS:
            raise ValueError(f'algoritmo já registrado: {nome}')
        ALGORITMOS[nome] = fabrica
        return fabrica

    return decorador


def criar(nome: str, hiperparametros: dict, seed: int) -> Previsor:
    """Instancia o previsor; `seed` só é repassada a quem a aceita."""
    fabrica = ALGORITMOS[nome]
    if getattr(fabrica, 'aceita_seed', False):
        return fabrica(**hiperparametros, seed=seed)
    return fabrica(**hiperparametros)


def _validar(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        raise ValueError('treino vazio')
    return y


@registrar('naive')
class Naive:
    """Repete o último valor observado."""

    def ajustar(self, y):
        self._ultimo = _validar(y)[-1]
        return self

    def prever(self, horizonte):
        return np.full(horizonte, self._ultimo)


@registrar('media_historica')
class MediaHistorica:
    """Média do treino do fold (janela expansiva)."""

    def ajustar(self, y):
        self._media = _validar(y).mean()
        return self

    def prever(self, horizonte):
        return np.full(horizonte, self._media)


@registrar('naive_sazonal')
class NaiveSazonal:
    """Repete o mesmo ponto do ciclo anterior (lag `periodo`)."""

    def __init__(self, periodo: int):
        if periodo < 1:
            raise ValueError('periodo deve ser >= 1')
        self.periodo = periodo

    def ajustar(self, y):
        y = _validar(y)
        if len(y) < self.periodo:
            raise ValueError('treino menor que o período sazonal')
        self._ciclo = y[-self.periodo :]
        return self

    def prever(self, horizonte):
        return np.resize(self._ciclo, horizonte)


from case_mr_health import algoritmos_prophet, algoritmos_statsmodels  # noqa: E402, F401
