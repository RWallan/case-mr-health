import duckdb

from case_mr_health.cli import app
from tests.conftest import escrever_planilhas


def test_preparar_dados_gera_base_e_relatorio(settings, planilhas):
    codigo = app(
        [
            'preparar-dados',
            '--raw-dir',
            str(settings.raw_dir),
            '--db-path',
            str(settings.db_path),
            '--relatorio-path',
            str(settings.relatorio_path),
            '--desenvolvimento-db-path',
            str(settings.desenvolvimento_db_path),
            '--oot-db-path',
            str(settings.oot_db_path),
        ],
        result_action='return_value',
    )

    assert codigo == 0
    assert settings.relatorio_path.read_text(encoding='utf-8').startswith(
        '# Relatório de qualidade'
    )
    con = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        [(n,)] = con.execute('SELECT count(*) FROM pedido').fetchall()
    finally:
        con.close()
    assert n == len(planilhas.pedidos)


def test_preparar_dados_devolve_erro_com_dados_invalidos(settings, planilhas):
    itens = [*planilhas.itens, (planilhas.pedidos[0][0], 'item A', -1)]
    escrever_planilhas(
        planilhas.raw_dir, planilhas.pedidos, itens, planilhas.precos
    )

    codigo = app(
        [
            'preparar-dados',
            '--raw-dir',
            str(settings.raw_dir),
            '--db-path',
            str(settings.db_path),
            '--desenvolvimento-db-path',
            str(settings.desenvolvimento_db_path),
            '--oot-db-path',
            str(settings.oot_db_path),
        ],
        result_action='return_value',
    )

    assert codigo == 1
    assert not settings.db_path.exists()
