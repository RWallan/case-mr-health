import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from loguru import logger

from case_mr_health.config import Settings
from case_mr_health.series import construir_series

CABECALHO_PEDIDO = ('ID_PEDIDO', 'DATA', 'VALOR_TOTAL')
CABECALHO_ITEM_PEDIDO = ('ID_PEDIDO', 'ID_ITEM', 'QUANTIDADE')
MAX_MENSAGENS = 20


class DadosInvalidosError(ValueError):
    """Planilhas com linhas que não podem entrar na base consolidada."""


@dataclass
class Verificacao:
    nome: str
    ok: bool
    valor: str
    detalhe: str = ''


@dataclass
class RelatorioQualidade:
    verificacoes: list[Verificacao] = field(default_factory=list)
    itens_repetidos: list[dict] = field(default_factory=list)

    def adicionar(
        self, nome: str, ok: bool, valor: object, detalhe: str = ''
    ) -> None:
        self.verificacoes.append(Verificacao(nome, ok, str(valor), detalhe))

    def em_markdown(self) -> str:
        linhas = [
            '# Relatório de qualidade',
            '',
            '| Verificação | Status | Valor | Detalhe |',
            '| --- | --- | --- | --- |',
        ]
        linhas += [
            f'| {v.nome} | {"ok" if v.ok else "alerta"} | {v.valor} '
            f'| {v.detalhe} |'
            for v in self.verificacoes
        ]
        linhas += [
            '',
            '## Itens de pedido repetidos (quantidades somadas)',
            '',
        ]
        if self.itens_repetidos:
            linhas += [
                '| Pedido | SKU | Linhas | Quantidades | Soma |',
                '| --- | --- | --- | --- | --- |',
            ]
            linhas += [
                f'| {r["id_pedido"]} | {r["sku"]} | {r["linhas"]} '
                f'| {r["quantidades"]} | {r["quantidade"]} |'
                for r in self.itens_repetidos
            ]
        else:
            linhas.append('Nenhum.')
        return '\n'.join(linhas) + '\n'


def preparar_dados(cfg: Settings | None = None) -> RelatorioQualidade:
    """Consolida as planilhas brutas em DuckDB e gera o relatório.

    As planilhas são só lidas. A base (`sku`, `pedido`, `item_pedido` e
    `base_consolidada`) e o relatório de qualidade são persistidos em
    `cfg.db_path`; o relatório também vai em markdown para
    `cfg.relatorio_path`. Linhas inválidas abortam a execução com
    `DadosInvalidosError`, sem escrever nada.
    """
    cfg = cfg or Settings()
    origens = {
        'pedido': cfg.raw_dir / cfg.arquivo_pedido,
        'item_pedido': cfg.raw_dir / cfg.arquivo_item_pedido,
        'sku': cfg.raw_dir / cfg.arquivo_sku,
    }
    faltantes = [str(p) for p in origens.values() if not p.is_file()]
    if faltantes:
        raise FileNotFoundError(f'Planilhas não encontradas: {faltantes}')
    hashes = {nome: _sha256(p) for nome, p in origens.items()}

    con = duckdb.connect()
    try:
        con.execute('INSTALL excel; LOAD excel')
        _carregar_brutos(con, origens)
        _validar(con)
        _consolidar(con)
        construir_series(con)
        relatorio = _relatorio(con, hashes)
        _persistir(con, relatorio, cfg)
    finally:
        con.close()

    if hashes != {nome: _sha256(p) for nome, p in origens.items()}:
        raise RuntimeError('Planilhas de origem foram alteradas.')
    logger.info('Base consolidada gravada em {}', cfg.db_path)
    return relatorio


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _ler_xlsx(con, caminho: Path, intervalo: str) -> str:
    # `header=false` + `all_varchar` evitam que o DuckDB descarte a coluna
    # de índice sem nome e converta tipos sem que possamos apontar a linha.
    return (
        f"read_xlsx('{caminho}', header=false, all_varchar=true, "
        f"range='{intervalo}')"
    )


def _carregar_brutos(con, origens: dict[str, Path]) -> None:
    for nome, ultima in (('pedido', 'D'), ('item_pedido', 'D')):
        leitura = _ler_xlsx(con, origens[nome], f'A1:{ultima}')
        con.execute(
            f'CREATE TABLE bruto_{nome} AS '
            f'SELECT row_number() OVER () AS linha, A, B, C, D '
            f'FROM {leitura}'
        )
        cabecalho = con.execute(
            f'SELECT B, C, D FROM bruto_{nome} WHERE linha = 1'
        ).fetchone()
        esperado = (
            CABECALHO_PEDIDO if nome == 'pedido' else (CABECALHO_ITEM_PEDIDO)
        )
        if cabecalho != esperado:
            raise DadosInvalidosError(
                f'Cabeçalho inesperado em {origens[nome].name}: '
                f'{cabecalho}, esperado {esperado}.'
            )
        con.execute(
            f'DELETE FROM bruto_{nome} WHERE linha = 1 '
            f'OR (B IS NULL AND C IS NULL AND D IS NULL)'
        )
    # A primeira linha de ITENS é um resquício (índice 0), não um dado.
    leitura = _ler_xlsx(con, origens['sku'], 'A1:B')
    con.execute(
        f'CREATE TABLE bruto_sku AS SELECT row_number() OVER () AS linha, '
        f'A, B FROM {leitura}'
    )
    con.execute('DELETE FROM bruto_sku WHERE linha = 1 OR A IS NULL')


def _validar(con) -> None:
    problemas: list[str] = []

    def coletar(sql: str, mensagem: str) -> None:
        for linha, *valores in con.execute(sql).fetchall():
            problemas.append(mensagem.format(linha=linha, v=valores))

    coletar(
        'SELECT linha, B FROM bruto_pedido '
        'WHERE try_cast(B AS BIGINT) IS NULL',
        'PEDIDO linha {linha}: ID_PEDIDO inválido {v[0]!r}.',
    )
    coletar(
        'SELECT linha, C FROM bruto_pedido '
        "WHERE C IS NULL OR NOT regexp_matches(C, '^\\d{4}-\\d{2}-\\d{2}$') "
        'OR try_cast(C AS DATE) IS NULL',
        'PEDIDO linha {linha}: data inválida {v[0]!r}.',
    )
    coletar(
        'SELECT min(linha), B FROM bruto_pedido GROUP BY B '
        'HAVING count(*) > 1',
        'PEDIDO linha {linha}: ID_PEDIDO {v[0]!r} duplicado.',
    )
    coletar(
        'SELECT linha, B FROM bruto_item_pedido '
        'WHERE try_cast(B AS BIGINT) IS NULL',
        'ITEM_PEDIDO linha {linha}: ID_PEDIDO inválido {v[0]!r}.',
    )
    coletar(
        'SELECT i.linha, i.B FROM bruto_item_pedido i '
        'LEFT JOIN bruto_pedido p ON p.B = i.B '
        'WHERE p.B IS NULL AND try_cast(i.B AS BIGINT) IS NOT NULL',
        'ITEM_PEDIDO linha {linha}: pedido {v[0]!r} sem registro em PEDIDO.',
    )
    coletar(
        'SELECT i.linha, i.C FROM bruto_item_pedido i '
        'LEFT JOIN bruto_sku s ON s.A = i.C WHERE s.A IS NULL',
        'ITEM_PEDIDO linha {linha}: SKU {v[0]!r} sem cadastro.',
    )
    coletar(
        'SELECT linha, D FROM bruto_item_pedido '
        'WHERE try_cast(D AS DOUBLE) < 0',
        'ITEM_PEDIDO linha {linha}: quantidade negativa {v[0]!r}.',
    )
    coletar(
        'SELECT linha, D FROM bruto_item_pedido '
        'WHERE try_cast(D AS DOUBLE) IS NULL '
        'OR try_cast(D AS DOUBLE) % 1 <> 0',
        'ITEM_PEDIDO linha {linha}: quantidade não inteira {v[0]!r}.',
    )
    coletar(
        'SELECT linha, B FROM bruto_sku '
        'WHERE try_cast(B AS DOUBLE) IS NULL OR try_cast(B AS DOUBLE) < 0',
        'ITENS linha {linha}: valor unitário inválido {v[0]!r}.',
    )
    coletar(
        'SELECT min(linha), A FROM bruto_sku GROUP BY A HAVING count(*) > 1',
        'ITENS linha {linha}: SKU {v[0]!r} duplicado no cadastro.',
    )
    if problemas:
        exibidos = problemas[:MAX_MENSAGENS]
        if len(problemas) > MAX_MENSAGENS:
            exibidos.append(f'... e mais {len(problemas) - MAX_MENSAGENS}.')
        raise DadosInvalidosError(
            f'{len(problemas)} problema(s) nas planilhas:\n'
            + '\n'.join(exibidos)
        )


def _consolidar(con) -> None:
    con.execute(
        'CREATE TABLE sku AS SELECT A AS sku, '
        'CAST(B AS DOUBLE) AS valor_unitario FROM bruto_sku'
    )
    con.execute(
        'CREATE TABLE item_pedido AS '
        'SELECT id_pedido, sku, quantidade, valor_unitario, '
        'quantidade * valor_unitario AS valor_item, linhas_originais '
        'FROM (SELECT CAST(i.B AS BIGINT) AS id_pedido, i.C AS sku, '
        'CAST(sum(CAST(i.D AS DOUBLE)) AS BIGINT) AS quantidade, '
        's.valor_unitario, count(*) AS linhas_originais '
        'FROM bruto_item_pedido i JOIN sku s ON s.sku = i.C '
        'GROUP BY ALL)'
    )
    con.execute(
        'CREATE TABLE pedido AS '
        'SELECT CAST(p.B AS BIGINT) AS id_pedido, CAST(p.C AS DATE) AS data, '
        'coalesce(sum(i.valor_item), 0) AS valor_total '
        'FROM bruto_pedido p '
        'LEFT JOIN item_pedido i ON i.id_pedido = CAST(p.B AS BIGINT) '
        'GROUP BY ALL'
    )
    con.execute(
        'CREATE TABLE base_consolidada AS '
        'SELECT p.id_pedido, p.data, i.sku, i.quantidade, i.valor_unitario, '
        'i.valor_item, p.valor_total AS valor_total_pedido '
        'FROM item_pedido i JOIN pedido p USING (id_pedido) '
        'ORDER BY p.data, p.id_pedido, i.sku'
    )


def _um(con, sql: str):
    return con.execute(sql).fetchone()[0]


def _relatorio(con, hashes: dict[str, str]) -> RelatorioQualidade:
    r = RelatorioQualidade()
    _verificar_fontes(con, r, hashes)
    _verificar_nulos(con, r)
    _verificar_integridade(con, r)
    _verificar_cardinalidade(con, r)
    _verificar_repetidos(con, r)
    _verificar_joins(con, r)
    return r


def _verificar_fontes(con, r: RelatorioQualidade, hashes: dict) -> None:
    n_ped = _um(con, 'SELECT count(*) FROM bruto_pedido')
    n_lin = _um(con, 'SELECT count(*) FROM bruto_item_pedido')
    n_sku = _um(con, 'SELECT count(*) FROM bruto_sku')
    r.adicionar(
        'Linhas por fonte',
        True,
        f'pedido={n_ped}, item_pedido={n_lin}, sku={n_sku}',
    )
    r.adicionar(
        'Hash SHA-256 das planilhas',
        True,
        'ver detalhe',
        '; '.join(f'{k}={v[:12]}' for k, v in hashes.items()),
    )
    r.adicionar(
        'Tipos fora do esperado',
        True,
        0,
        'ID, data, quantidade e valor unitário convertem sem perda',
    )
    r.adicionar(
        'ID_PEDIDO único em PEDIDO',
        _um(con, 'SELECT count(DISTINCT id_pedido) FROM pedido') == n_ped,
        f'{n_ped} pedidos',
    )
    incoerentes = _um(
        con,
        'SELECT count(*) FROM pedido WHERE NOT '
        "(CAST(id_pedido AS VARCHAR) LIKE '%' || strftime(data, '%Y%m%d'))",
    )
    r.adicionar(
        'ID_PEDIDO termina na data do pedido (AAAAMMDD)',
        incoerentes == 0,
        incoerentes,
    )


def _verificar_nulos(con, r: RelatorioQualidade) -> None:
    colunas = (
        ('pedido', 'ID_PEDIDO', 'B'),
        ('pedido', 'DATA', 'C'),
        ('pedido', 'VALOR_TOTAL', 'D'),
        ('item_pedido', 'ID_ITEM', 'C'),
        ('item_pedido', 'QUANTIDADE', 'D'),
    )
    for fonte, nome, letra in colunas:
        total = _um(con, f'SELECT count(*) FROM bruto_{fonte}')
        n = _um(
            con, f'SELECT count(*) FROM bruto_{fonte} WHERE {letra} IS NULL'
        )
        vazia = bool(total) and n == total
        r.adicionar(
            f'Nulos em {fonte}.{nome}',
            n == 0,
            f'{n}/{total}',
            'coluna totalmente vazia; valor reconstruído dos itens'
            if vazia
            else '',
        )


def _verificar_integridade(con, r: RelatorioQualidade) -> None:
    sem_pedido = _um(
        con,
        'SELECT count(*) FROM bruto_item_pedido i LEFT JOIN bruto_pedido p '
        'ON p.B = i.B WHERE p.B IS NULL',
    )
    sem_sku = _um(
        con,
        'SELECT count(*) FROM bruto_item_pedido i LEFT JOIN bruto_sku s '
        'ON s.A = i.C WHERE s.A IS NULL',
    )
    sem_itens = _um(
        con,
        'SELECT count(*) FROM pedido p LEFT JOIN item_pedido i '
        'USING (id_pedido) WHERE i.id_pedido IS NULL',
    )
    r.adicionar('Itens de pedido sem pedido', sem_pedido == 0, sem_pedido)
    r.adicionar('Itens de pedido sem SKU no cadastro', sem_sku == 0, sem_sku)
    r.adicionar('Pedidos sem nenhum item', sem_itens == 0, sem_itens)


def _verificar_cardinalidade(con, r: RelatorioQualidade) -> None:
    c = con.execute(
        'SELECT min(n), median(n), max(n) FROM '
        '(SELECT count(*) AS n FROM item_pedido GROUP BY id_pedido)'
    ).fetchone()
    r.adicionar(
        'Cardinalidade pedido → SKUs distintos (mín/mediana/máx)',
        True,
        f'{c[0]:g}/{c[1]:g}/{c[2]:g}',
        'um pedido tem N itens; cada item pertence a um único pedido',
    )
    c = con.execute(
        'SELECT min(n), median(n), max(n), count(*) FROM '
        '(SELECT count(*) AS n FROM pedido GROUP BY data)'
    ).fetchone()
    r.adicionar(
        'Cardinalidade dia → pedidos (mín/mediana/máx)',
        True,
        f'{c[0]:g}/{c[1]:g}/{c[2]:g}',
        f'{c[3]} dias com ao menos um pedido',
    )
    ini, fim = con.execute(
        'SELECT min(data), max(data) FROM pedido'
    ).fetchone()
    r.adicionar('Período dos pedidos', True, f'{ini} a {fim}')


def _verificar_repetidos(con, r: RelatorioQualidade) -> None:
    rep = con.execute(
        'SELECT i.id_pedido, i.sku, i.linhas_originais, i.quantidade, '
        "(SELECT string_agg(b.D, '+' ORDER BY b.linha) "
        ' FROM bruto_item_pedido b '
        ' WHERE CAST(b.B AS BIGINT) = i.id_pedido AND b.C = i.sku) '
        'FROM item_pedido i WHERE i.linhas_originais > 1 '
        'ORDER BY i.id_pedido, i.sku'
    ).fetchall()
    r.itens_repetidos = [
        {
            'id_pedido': pedido,
            'sku': sku,
            'linhas': linhas,
            'quantidade': soma,
            'quantidades': quantidades,
        }
        for pedido, sku, linhas, soma, quantidades in rep
    ]
    r.adicionar(
        'Pares (pedido, SKU) repetidos',
        not rep,
        len(rep),
        'quantidades somadas; lista abaixo',
    )


def _verificar_joins(con, r: RelatorioQualidade) -> None:
    n_lin = _um(con, 'SELECT count(*) FROM bruto_item_pedido')
    qtd_bruta = _um(
        con, 'SELECT sum(CAST(D AS DOUBLE)) FROM bruto_item_pedido'
    )
    qtd_base = _um(con, 'SELECT sum(quantidade) FROM base_consolidada')
    n_base = _um(con, 'SELECT count(*) FROM base_consolidada')
    n_pares = _um(con, 'SELECT count(*) FROM item_pedido')
    r.adicionar(
        'Perda nos joins: quantidade total',
        qtd_bruta == qtd_base,
        f'{qtd_bruta:g} → {qtd_base}',
    )
    r.adicionar(
        'Perda nos joins: linhas (após soma de repetidos)',
        n_pares == n_base,
        f'{n_lin} linhas brutas → {n_pares} pares → {n_base} na base',
    )
    divergentes = _um(
        con,
        'SELECT count(*) FROM base_consolidada b JOIN sku s USING (sku) '
        'WHERE b.valor_unitario <> s.valor_unitario',
    )
    r.adicionar(
        'Valor unitário da base igual ao cadastro',
        divergentes == 0,
        divergentes,
    )
    soma_itens = _um(con, 'SELECT sum(valor_item) FROM base_consolidada')
    soma_pedidos = _um(con, 'SELECT sum(valor_total) FROM pedido')
    r.adicionar(
        'Soma dos valores dos pedidos = soma dos valores dos itens',
        soma_itens == soma_pedidos,
        f'{soma_pedidos:g}',
    )


def _persistir(con, relatorio: RelatorioQualidade, cfg: Settings) -> None:
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        'CREATE TABLE qualidade_verificacoes '
        '(nome VARCHAR, ok BOOLEAN, valor VARCHAR, detalhe VARCHAR)'
    )
    con.executemany(
        'INSERT INTO qualidade_verificacoes VALUES (?, ?, ?, ?)',
        [(v.nome, v.ok, v.valor, v.detalhe) for v in relatorio.verificacoes],
    )
    con.execute(
        'CREATE TABLE qualidade_itens_repetidos AS '
        'SELECT id_pedido, sku, linhas_originais AS linhas, quantidade '
        'FROM item_pedido WHERE linhas_originais > 1'
    )
    con.execute(f"ATTACH '{cfg.db_path}' AS destino")
    for tabela in (
        'sku',
        'pedido',
        'item_pedido',
        'base_consolidada',
        'serie_diaria',
        'serie_semanal',
        'qualidade_verificacoes',
        'qualidade_itens_repetidos',
    ):
        con.execute(
            f'CREATE OR REPLACE TABLE destino.{tabela} AS '
            f'SELECT * FROM {tabela}'
        )
    con.execute('DETACH destino')
    cfg.relatorio_path.write_text(relatorio.em_markdown(), encoding='utf-8')
