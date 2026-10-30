import hashlib

import duckdb
import pytest

from case_mr_health.dados import DadosInvalidosError, preparar_dados
from tests.conftest import escrever_planilhas


def _consultar(settings, sql):
    con = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _hashes(raw_dir):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in raw_dir.glob('*.xlsx')
    }


def test_nao_perde_linhas_nem_quantidade_nos_joins(settings, planilhas):
    preparar_dados(settings)

    [(n_pedidos,)] = _consultar(settings, 'SELECT count(*) FROM pedido')
    [(quantidade,)] = _consultar(
        settings, 'SELECT sum(quantidade) FROM base_consolidada'
    )
    [(n_base,)] = _consultar(settings, 'SELECT count(*) FROM base_consolidada')
    assert n_pedidos == len(planilhas.pedidos)
    assert quantidade == planilhas.quantidade_total
    assert n_base == len(planilhas.quantidade_por_par)


def test_soma_quantidades_de_itens_repetidos(settings, planilhas):
    preparar_dados(settings)

    linhas = _consultar(
        settings, 'SELECT id_pedido, sku, quantidade FROM item_pedido'
    )
    obtido = {(pedido, sku): qtd for pedido, sku, qtd in linhas}
    assert obtido == planilhas.quantidade_por_par
    assert planilhas.pares_repetidos


def test_relatorio_lista_itens_repetidos(settings, planilhas):
    relatorio = preparar_dados(settings)

    listados = {(r['id_pedido'], r['sku']) for r in relatorio.itens_repetidos}
    assert listados == planilhas.pares_repetidos
    texto = settings.relatorio_path.read_text(encoding='utf-8')
    for id_pedido, sku in planilhas.pares_repetidos:
        assert f'| {id_pedido} | {sku} |' in texto


def test_valor_total_do_pedido_e_soma_dos_valores_dos_itens(
    settings, planilhas
):
    preparar_dados(settings)

    linhas = _consultar(settings, 'SELECT id_pedido, valor_total FROM pedido')
    assert dict(linhas) == planilhas.valor_por_pedido


def test_valor_do_item_usa_valor_unitario_do_cadastro(settings, planilhas):
    preparar_dados(settings)

    linhas = _consultar(
        settings,
        'SELECT sku, quantidade, valor_unitario, valor_item '
        'FROM base_consolidada',
    )
    for sku, quantidade, valor_unitario, valor_item in linhas:
        assert valor_unitario == planilhas.precos[sku]
        assert valor_item == quantidade * planilhas.precos[sku]


def test_relatorio_tem_verificacoes_de_qualidade_sem_alerta_de_integridade(
    settings,
):
    relatorio = preparar_dados(settings)

    por_nome = {v.nome: v for v in relatorio.verificacoes}
    assert por_nome['Itens de pedido sem pedido'].ok
    assert por_nome['Itens de pedido sem SKU no cadastro'].ok
    assert por_nome['Perda nos joins: quantidade total'].ok
    assert not por_nome['Nulos em pedido.VALOR_TOTAL'].ok
    assert not por_nome['Pares (pedido, SKU) repetidos'].ok


def test_planilhas_originais_ficam_intocadas(settings, planilhas):
    antes = _hashes(planilhas.raw_dir)

    preparar_dados(settings)

    assert _hashes(planilhas.raw_dir) == antes


def _reescrever(planilhas, **alteracoes):
    pedidos = alteracoes.get('pedidos', planilhas.pedidos)
    itens = alteracoes.get('itens', planilhas.itens)
    escrever_planilhas(planilhas.raw_dir, pedidos, itens, planilhas.precos)


def test_rejeita_sku_sem_cadastro(settings, planilhas):
    id_pedido = planilhas.pedidos[0][0]
    _reescrever(planilhas, itens=[*planilhas.itens, (id_pedido, 'item Z', 1)])

    with pytest.raises(DadosInvalidosError, match="SKU 'item Z' sem cadastro"):
        preparar_dados(settings)
    assert not settings.db_path.exists()


def test_rejeita_quantidade_negativa(settings, planilhas):
    id_pedido = planilhas.pedidos[0][0]
    _reescrever(planilhas, itens=[*planilhas.itens, (id_pedido, 'item A', -2)])

    with pytest.raises(DadosInvalidosError, match='quantidade negativa'):
        preparar_dados(settings)


@pytest.mark.parametrize('data', ['2021-02-30', '01/06/2021', 'ontem'])
def test_rejeita_data_invalida(settings, planilhas, data):
    pedidos = [*planilhas.pedidos, (999920210601, data)]
    itens = [*planilhas.itens, (999920210601, 'item A', 1)]
    _reescrever(planilhas, pedidos=pedidos, itens=itens)

    with pytest.raises(DadosInvalidosError, match='data inválida'):
        preparar_dados(settings)


def test_mensagem_de_erro_aponta_a_linha_da_planilha(settings, planilhas):
    id_pedido = planilhas.pedidos[0][0]
    _reescrever(planilhas, itens=[*planilhas.itens, (id_pedido, 'item A', -2)])
    linha_esperada = len(planilhas.itens) + 2  # cabeçalho + 1-indexado

    with pytest.raises(DadosInvalidosError) as erro:
        preparar_dados(settings)
    assert f'ITEM_PEDIDO linha {linha_esperada}' in str(erro.value)


def test_rejeita_item_de_pedido_inexistente(settings, planilhas):
    _reescrever(
        planilhas, itens=[*planilhas.itens, (123420210601, 'item A', 1)]
    )

    with pytest.raises(DadosInvalidosError, match='sem registro em PEDIDO'):
        preparar_dados(settings)


def test_falha_com_planilha_ausente(settings, planilhas):
    (planilhas.raw_dir / 'ITENS-_3_.xlsx').unlink()

    with pytest.raises(FileNotFoundError):
        preparar_dados(settings)
