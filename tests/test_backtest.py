from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from case_mr_health import algoritmos
from case_mr_health.backtest import rodar_backtest
from case_mr_health.particoes import Fold, Particao

INICIO = date(2021, 6, 7)  # segunda-feira
NIVEL = 3
SEMANA_ATIPICA = 6  # índice da semana 07-19


def _particao(sku, gran, n, treino_min, passo=1) -> Particao:
    """Folds de origem móvel sobre `n` períodos de 1 semana (ou dia)."""
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


def _serie(valores, gran='semanal') -> pd.Series:
    passo = pd.Timedelta(
        weeks=1 if gran == 'semanal' else 0, days=0 if gran == 'semanal' else 1
    )
    return pd.Series(
        valores,
        index=pd.DatetimeIndex([
            INICIO + i * passo for i in range(len(valores))
        ]),
        dtype=float,
    )


def test_naive_em_serie_crescente_confere_com_a_mao():
    # treino 1..n, teste n+1: erro do naive = 1; da média = (n+1)/2.
    serie = _serie(range(1, 9))
    particao = _particao('item A', 'semanal', 8, treino_min=4)

    naive = rodar_backtest(serie, particao, 'naive', {}, seed=1)
    media = rodar_backtest(serie, particao, 'media_historica', {}, seed=1)

    assert [f.metricas['mae'] for f in naive.folds] == [1, 1, 1, 1]
    assert naive.medias['mase'] == pytest.approx(1.0)  # escala = 1
    assert [f.metricas['mae'] for f in media.folds] == [2.5, 3, 3.5, 4]
    assert media.medias['mae'] == pytest.approx(3.25)


def test_cada_fold_ajusta_so_com_o_treino_do_fold(monkeypatch):
    vistos = []

    class Espiao:
        def ajustar(self, y):
            vistos.append(len(y))
            return self

        @staticmethod
        def prever(horizonte):
            return np.zeros(horizonte)

    monkeypatch.setattr(algoritmos, 'ALGORITMOS', {'espiao': Espiao})

    rodar_backtest(
        _serie(range(10)),
        _particao('item A', 'semanal', 10, 4),
        'espiao',
        {},
        1,
    )

    assert vistos == [4, 5, 6, 7, 8, 9]


def test_previsoes_sao_truncadas_em_zero(monkeypatch):
    class Negativo:
        def ajustar(self, y):
            return self

        @staticmethod
        def prever(horizonte):
            return np.full(horizonte, -5.0)

    monkeypatch.setattr(algoritmos, 'ALGORITMOS', {'negativo': Negativo})

    resultado = rodar_backtest(
        _serie([NIVEL] * 6),
        _particao('item A', 'semanal', 6, 4),
        'negativo',
        {},
        1,
    )

    assert all(p == 0 for f in resultado.folds for p in f.previsto)
    assert resultado.medias['mae'] == NIVEL


def test_sensibilidade_do_item_c_semanal_confere_com_a_mao():
    # Semana 07-19 (índice 6) vale 40; as outras, 10. Naive erra 30 nos
    # folds 1 e 2 e 0 nos demais.
    valores = [40 if i == SEMANA_ATIPICA else 10 for i in range(11)]
    particao = _particao('item C', 'semanal', 11, treino_min=SEMANA_ATIPICA)
    assert particao.folds[0].teste_inicio == date(2021, 7, 19)

    resultado = rodar_backtest(_serie(valores), particao, 'naive', {}, 1)

    assert resultado.medias['mae'] == pytest.approx(12.0)
    sens = resultado.sensibilidade
    assert sens['sem_periodo_atipico']['mae'] == pytest.approx(7.5)
    assert sens['sem_folds_1_2']['mae'] == pytest.approx(0.0)


def test_outras_series_nao_tem_sensibilidade():
    resultado = rodar_backtest(
        _serie(range(8)), _particao('item A', 'semanal', 8, 4), 'naive', {}, 1
    )

    assert resultado.sensibilidade == {}


def test_serie_sem_folds_e_rejeitada():
    particao = _particao('item A', 'semanal', 4, treino_min=4)

    with pytest.raises(ValueError, match='sem folds'):
        rodar_backtest(_serie(range(4)), particao, 'naive', {}, 1)
