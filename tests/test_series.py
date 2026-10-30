from collections import defaultdict
from datetime import date, timedelta

import duckdb
import pytest

from case_mr_health.dados import preparar_dados


@pytest.fixture
def banco(settings):
    preparar_dados(settings)
    con = duckdb.connect(str(settings.db_path), read_only=True)
    yield con
    con.close()


@pytest.fixture
def esperado(planilhas):
    """Vendas por (SKU, dia), calculadas à parte do pipeline."""
    data_do_pedido = {
        id_pedido: date.fromisoformat(data)
        for id_pedido, data in planilhas.pedidos
    }
    vendas: dict[tuple[str, date], int] = defaultdict(int)
    for id_pedido, sku, qtd in planilhas.itens:
        vendas[sku, data_do_pedido[id_pedido]] += qtd
    return vendas, max(data_do_pedido.values())


def _diaria(banco):
    return banco.execute(
        'SELECT sku, data, quantidade, imputado FROM serie_diaria'
    ).fetchall()


def test_calendario_do_sku_vai_da_primeira_venda_ao_fim_da_rede(
    banco, esperado
):
    vendas, fim = esperado
    por_sku = defaultdict(list)
    for sku, data, _, _ in _diaria(banco):
        por_sku[sku].append(data)

    for sku, datas in por_sku.items():
        inicio = min(d for (s, d) in vendas if s == sku)
        dias = (fim - inicio).days + 1
        assert sorted(datas) == [inicio + timedelta(i) for i in range(dias)]


def test_dia_sem_venda_vira_zero_imputado_e_venda_nao_e_marcada(
    banco, esperado
):
    vendas, _ = esperado

    for sku, data, quantidade, imputado in _diaria(banco):
        if (sku, data) in vendas:
            assert (quantidade, imputado) == (vendas[sku, data], False)
        else:
            assert (quantidade, imputado) == (0, True)


def test_semanas_vao_de_segunda_a_domingo_e_so_as_completas(banco, esperado):
    vendas, fim = esperado
    semanal = banco.execute('SELECT sku, semana FROM serie_semanal').fetchall()
    assert semanal
    assert all(semana.weekday() == 0 for _, semana in semanal)

    esperadas = set()
    for sku in {s for s, _ in vendas}:
        inicio = min(d for (s, d) in vendas if s == sku)
        segunda = inicio - timedelta(days=inicio.weekday())
        while segunda + timedelta(days=6) <= fim:
            if segunda >= inicio:
                esperadas.add((sku, segunda))
            segunda += timedelta(days=7)
    assert set(semanal) == esperadas


def test_soma_diaria_de_cada_semana_completa_e_igual_ao_valor_semanal(
    banco,
):
    divergencias = banco.execute(
        'SELECT w.sku, w.semana FROM serie_semanal w '
        'JOIN serie_diaria d ON d.sku = w.sku '
        'AND d.data BETWEEN w.semana AND w.semana + 6 '
        'GROUP BY w.sku, w.semana, w.quantidade '
        'HAVING sum(d.quantidade) <> w.quantidade OR count(*) <> 7'
    ).fetchall()

    assert divergencias == []
