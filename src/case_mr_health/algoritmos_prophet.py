"""Candidato Prophet: só sazonalidade semanal (#11, ADR 0010).

O contrato `ajustar(y)` não recebe datas. Aqui a série ganha um calendário
sintético de dias consecutivos, com início fixo. Isso basta: a sazonalidade
é uma soma de Fourier de período 7 com coeficientes livres e priori
isotrópica, então trocar o início só gira a fase, e a posição no ciclo
continua sendo aprendida dos dados. O previsto depende da posição, que é
contígua porque a série diária não tem buracos (zeros imputados); o nome do
dia da semana não é usado em lugar nenhum.

O artefato guarda o modelo pelo `model_to_json`, o formato de serialização
do Prophet, sem o backend do Stan (que aponta para arquivos locais).
"""

import logging
from typing import Self

import numpy as np
import pandas as pd

from case_mr_health.algoritmos import _validar, registrar
from case_mr_health.algoritmos_statsmodels import (
    DiagnosticoAjuste,
    ajustar_monitorado,
    publicar_diagnostico,
    verificar_sazonalidade,
)

INICIO_CALENDARIO = '2000-01-03'
PERIODO_SEMANAL = 7
AMOSTRAS_INTERVALO = 1000


def _classe_prophet():
    """Importa só quando precisa (lento) e cala o log de cada ajuste."""
    logging.getLogger('prophet').setLevel(logging.CRITICAL)
    from prophet import Prophet  # noqa: PLC0415

    logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
    return Prophet


def _serializar(modelo) -> str:
    from prophet.serialize import model_to_json  # noqa: PLC0415

    return model_to_json(modelo)


def _desserializar(texto: str):
    _classe_prophet()
    from prophet.serialize import model_from_json  # noqa: PLC0415

    return model_from_json(texto)


def _convergiu(modelo) -> bool:
    """Série constante não passa pelo Stan; nesse caso não há otimização."""
    ajuste = getattr(modelo.stan_backend, 'stan_fit', None)
    return ajuste is None or bool(ajuste.converged)


@registrar('prophet')
class ProphetSemanal:
    """Tendência linear sem pontos de mudança e sazonalidade semanal."""

    aceita_seed = True
    dependencias = ('numpy', 'pandas', 'prophet')

    def __init__(
        self,
        ordem_fourier: int,
        escala_sazonalidade: float,
        seed: int = 0,
    ):
        self.ordem_fourier = int(ordem_fourier)
        self.escala_sazonalidade = float(escala_sazonalidade)
        self.seed = seed

    def _hiperparametros(self) -> dict:
        return {
            'ordem_fourier': self.ordem_fourier,
            'escala_sazonalidade': self.escala_sazonalidade,
        }

    def _estimar(self, y: np.ndarray):
        modelo = _classe_prophet()(
            growth='linear',
            n_changepoints=0,
            yearly_seasonality=False,
            weekly_seasonality=self.ordem_fourier,
            daily_seasonality=False,
            seasonality_mode='additive',
            seasonality_prior_scale=self.escala_sazonalidade,
            uncertainty_samples=0,
        )
        return modelo.fit(
            pd.DataFrame({
                'ds': pd.date_range(
                    INICIO_CALENDARIO, periods=len(y), freq='D'
                ),
                'y': y,
            }),
            seed=self.seed,
        )

    def ajustar(self, y) -> Self:
        y = _validar(y)
        self._modelo, avisos = ajustar_monitorado(
            'prophet',
            self._hiperparametros(),
            len(y),
            lambda: self._estimar(y),
            _convergiu,
        )
        self.diagnostico = DiagnosticoAjuste(
            'prophet',
            len(y),
            True,
            avisos,
            (verificar_sazonalidade(y, PERIODO_SEMANAL),),
        )
        publicar_diagnostico(self.diagnostico)
        return self

    def _futuro(self, horizonte: int) -> pd.DataFrame:
        return self._modelo.make_future_dataframe(
            periods=horizonte, freq='D', include_history=False
        )

    def prever(self, horizonte):
        previsao = self._modelo.predict(self._futuro(horizonte))
        return previsao['yhat'].to_numpy(dtype=float)

    def intervalos_nativos(
        self, horizonte: int, niveis: tuple[float, ...]
    ) -> dict[float, tuple[np.ndarray, np.ndarray]]:
        """Quantis da simulação do Prophet, reprodutíveis pela seed.

        Sem MCMC e sem pontos de mudança, a simulação só traz o ruído da
        observação: a largura não cresce com o horizonte.
        """
        estado = np.random.get_state()
        np.random.seed(self.seed)  # noqa: NPY002
        self._modelo.uncertainty_samples = AMOSTRAS_INTERVALO
        try:
            amostras = self._modelo.predictive_samples(self._futuro(horizonte))
        finally:
            self._modelo.uncertainty_samples = 0
            np.random.set_state(estado)
        return {
            nivel: (
                np.quantile(amostras['yhat'], (1 - nivel) / 2, axis=1),
                np.quantile(amostras['yhat'], (1 + nivel) / 2, axis=1),
            )
            for nivel in niveis
        }

    def __getstate__(self) -> dict:
        estado = dict(self.__dict__)
        if '_modelo' in estado:
            estado['_modelo'] = _serializar(estado['_modelo'])
        return estado

    def __setstate__(self, estado: dict) -> None:
        self.__dict__.update(estado)
        if '_modelo' in estado:
            self._modelo = _desserializar(estado['_modelo'])
