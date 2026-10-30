"""Métodos de demanda intermitente: Croston, SBA e TSB (#10).

Implementação própria, sem `numba` nem `statsforecast` (ADR 0003). A
previsão é uma taxa de demanda por período, constante no horizonte e não
negativa. Fontes e decisões: `docs/relatorio/fase2/10.md`.

Recursões, com `z` o tamanho da demanda, `x` o intervalo entre demandas e
`p` a probabilidade de demanda:

- Croston (1972): `z` e `x` são atualizados só nos períodos com demanda, com
  o mesmo `alfa`; a previsão é `z / x`.
- SBA (Syntetos e Boylan): a previsão do Croston vezes `1 - alfa / 2`.
- TSB (Teunter, Syntetos e Babai, 2011): `p` é atualizado em todo período e
  `z`, só com demanda; a previsão é `p * z`. O `alfa_beta` é o mesmo para os
  dois (D-004).

Inicialização, opção `'mean'` do pacote R `tsintermittent`: `z` começa na
primeira demanda, `x` na média dos intervalos do treino e `p` na fração de
períodos com demanda do treino. O primeiro intervalo conta desde o início da
série. O motivo: o calendário do SKU começa na primeira venda, logo o
primeiro intervalo é sempre 1 e iniciar `x` nele enviesaria a previsão para
cima em treinos curtos. Só o treino do fold é usado.

Sem nenhuma demanda no treino, a previsão é zero. O Croston e o SBA mantêm a
limitação do método: os zeros depois da última demanda não alteram a
previsão, o que o TSB corrige.
"""

import numpy as np

from case_mr_health import algoritmos


def _demanda(y: np.ndarray) -> np.ndarray:
    y = algoritmos._validar(y)
    if not (y >= 0).all():
        raise ValueError('demanda negativa ou ausente no treino')
    return y


def _peso(nome: str, valor: float) -> float:
    if not 0 < valor <= 1:
        raise ValueError(f'{nome} deve estar em (0, 1]')
    return valor


def _suavizar(inicial: float, valores: np.ndarray, peso: float) -> float:
    """Suavização exponencial simples a partir de `inicial`."""
    estado = float(inicial)
    for valor in valores:
        estado += peso * (float(valor) - estado)
    return estado


class _TaxaConstante:
    """Prevê no horizonte a taxa calculada em `ajustar`."""

    def prever(self, horizonte):
        return np.full(horizonte, self._taxa)


@algoritmos.registrar('croston')
class Croston(_TaxaConstante):
    """Tamanho suavizado dividido pelo intervalo suavizado."""

    def __init__(self, alfa: float):
        self.alfa = _peso('alfa', alfa)

    def ajustar(self, y):
        y = _demanda(y)
        posicoes = np.flatnonzero(y)
        if posicoes.size == 0:
            self._taxa = 0.0
            return self
        tamanhos = y[posicoes]
        intervalos = np.diff(posicoes, prepend=-1)
        tamanho = _suavizar(tamanhos[0], tamanhos[1:], self.alfa)
        intervalo = _suavizar(intervalos.mean(), intervalos[1:], self.alfa)
        self._taxa = tamanho / intervalo
        return self


@algoritmos.registrar('sba')
class SBA(Croston):
    """Croston com a correção de viés de Syntetos e Boylan."""

    def ajustar(self, y):
        super().ajustar(y)
        self._taxa *= 1 - self.alfa / 2
        return self


@algoritmos.registrar('tsb')
class TSB(_TaxaConstante):
    """Probabilidade de demanda vezes o tamanho suavizado."""

    def __init__(self, alfa_beta: float):
        self.alfa_beta = _peso('alfa_beta', alfa_beta)

    def ajustar(self, y):
        y = _demanda(y)
        ocorreu = y > 0
        if not ocorreu.any():
            self._taxa = 0.0
            return self
        tamanhos = y[ocorreu]
        tamanho = _suavizar(tamanhos[0], tamanhos[1:], self.alfa_beta)
        probabilidade = _suavizar(ocorreu.mean(), ocorreu[1:], self.alfa_beta)
        self._taxa = probabilidade * tamanho
        return self
