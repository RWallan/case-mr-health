import math

import pytest

from case_mr_health import metricas

OBSERVADO = [3, 0, 2, 5]
PREVISTO = [2, 1, 2, 3]
TREINO = [1, 3, 2, 4]  # diferenças absolutas: 2, 1, 2 -> escala 5/3


def test_metricas_conferem_com_o_calculo_a_mao():
    resultado = metricas.calcular(OBSERVADO, PREVISTO, TREINO)

    assert resultado['mae'] == pytest.approx(1.0)  # (1+1+0+2)/4
    assert resultado['mse'] == pytest.approx(1.5)  # (1+1+0+4)/4
    assert resultado['rmse'] == pytest.approx(math.sqrt(1.5))
    assert resultado['wape'] == pytest.approx(0.4)  # 4 / 10
    assert resultado['mase'] == pytest.approx(0.6)  # 1 / (5/3)


def test_wape_indefinido_quando_nao_ha_venda_no_fold():
    assert math.isnan(metricas.wape([0, 0], [1, 1]))


@pytest.mark.parametrize('treino', [[4, 4, 4], [7]])
def test_mase_indefinido_com_escala_zero_ou_treino_curto(treino):
    assert math.isnan(metricas.mase(OBSERVADO, PREVISTO, treino))


def test_tamanhos_diferentes_sao_rejeitados():
    with pytest.raises(ValueError, match='mesmo tamanho'):
        metricas.mae([1, 2], [1])
