"""Ingestão de pedidos novos na base consolidada (#28, ADR 0011).

Recebe a planilha de pedidos e a de itens de pedido, no formato das brutas,
valida com as regras de `dados.py` (erros com planilha e linha), acrescenta
só os pedidos novos e reconstrói as séries completas em `cfg.db_path`. Não
toca na visão de desenvolvimento nem no OOT, que seguem como evidência da
avaliação final. Cada atualização guarda o hash dos dados que a gerou.
"""

import hashlib
import shutil
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from loguru import logger

from case_mr_health.config import Settings
from case_mr_health.dados import (
    MAX_MENSAGENS,
    DadosInvalidosError,
    _carregar_bruto,
    _consolidar,
    _validar,
)
from case_mr_health.series import construir_series

HASH_INICIAL = 'base'
# DuckDB não abre o mesmo arquivo com configurações diferentes no mesmo
# processo; quem lê ou escreve `cfg.db_path` na API passa por esta trava.
ACESSO_BASE = threading.RLock()
_TABELAS_NOVAS = ('item_pedido', 'pedido', 'base_consolidada')
_CRIAR_ATUALIZACOES = """
CREATE TABLE IF NOT EXISTS atualizacoes (
    hash_dados VARCHAR PRIMARY KEY,
    hash_pedido VARCHAR NOT NULL,
    hash_itens VARCHAR NOT NULL,
    aplicada_em TIMESTAMP NOT NULL,
    pedidos_novos INTEGER NOT NULL,
    itens_novos INTEGER NOT NULL,
    ultimo_dia DATE NOT NULL
)
"""


class AtualizacaoRepetidaError(ValueError):
    """O par de arquivos já foi aplicado à base."""


@dataclass(frozen=True)
class Ingestao:
    hash_dados: str
    hash_pedido: str
    hash_itens: str
    pedidos_novos: int
    itens_novos: int
    ultimo_dia: date


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def hash_dados_atual(cfg: Settings) -> str:
    """Hash da última atualização aplicada, ou `base` se não houve."""
    with ACESSO_BASE, duckdb.connect(str(cfg.db_path), read_only=True) as con:
        existe = con.execute(
            'SELECT count(*) FROM information_schema.tables '
            "WHERE table_name = 'atualizacoes'"
        ).fetchone()[0]
        if not existe:
            return HASH_INICIAL
        linha = con.execute(
            'SELECT hash_dados FROM atualizacoes '
            'ORDER BY aplicada_em DESC LIMIT 1'
        ).fetchone()
    return linha[0] if linha else HASH_INICIAL


def ingerir_pedidos(cfg: Settings, pedidos: Path, itens: Path) -> Ingestao:
    """Valida e acrescenta os pedidos novos; tudo ou nada.

    Levanta `DadosInvalidosError` (planilha e linha de cada problema) e
    `AtualizacaoRepetidaError` (par de arquivos já aplicado).
    """
    hash_pedido, hash_itens = _sha256(pedidos), _sha256(itens)
    with ACESSO_BASE:
        ingestao = _ingerir(cfg, pedidos, itens, (hash_pedido, hash_itens))
    _guardar_copias(cfg, ingestao.hash_dados, pedidos, itens)
    logger.info(
        'Atualização {}: {} pedidos e {} itens novos',
        ingestao.hash_dados[:12],
        ingestao.pedidos_novos,
        ingestao.itens_novos,
    )
    return ingestao


def _ingerir(
    cfg: Settings, pedidos: Path, itens: Path, hashes: tuple[str, str]
) -> Ingestao:
    hash_pedido, hash_itens = hashes
    base = duckdb.connect(str(cfg.db_path))
    try:
        base.execute(_CRIAR_ATUALIZACOES)
        _recusar_repetida(base, hash_pedido, hash_itens)
        novos = _validar_e_consolidar(base, pedidos, itens)
        anterior = _hash_anterior(base)
        hash_dados = hashlib.sha256(
            f'{anterior}|{hash_pedido}|{hash_itens}'.encode()
        ).hexdigest()
        base.execute('BEGIN')
        try:
            ultimo_dia = _aplicar(
                base, novos, (hash_dados, hash_pedido, hash_itens)
            )
            base.execute('COMMIT')
        except Exception:
            base.execute('ROLLBACK')
            raise
    finally:
        base.close()
    return Ingestao(
        hash_dados,
        hash_pedido,
        hash_itens,
        len(novos['pedido']),
        len(novos['item_pedido']),
        ultimo_dia,
    )


def _aplicar(base, novos: dict, hashes: tuple[str, str, str]) -> date:
    """Acrescenta as linhas, refaz as séries e registra a atualização."""
    _acrescentar(base, novos)
    base.execute('DROP TABLE serie_diaria')
    base.execute('DROP TABLE serie_semanal')
    construir_series(base)
    ultimo_dia = base.execute('SELECT max(data) FROM pedido').fetchone()[0]
    base.execute(
        'INSERT INTO atualizacoes VALUES (?, ?, ?, ?, ?, ?, ?)',
        [
            *hashes,
            datetime.now(UTC).replace(tzinfo=None),
            len(novos['pedido']),
            len(novos['item_pedido']),
            ultimo_dia,
        ],
    )
    return ultimo_dia


def _recusar_repetida(base, hash_pedido: str, hash_itens: str) -> None:
    repetida = base.execute(
        'SELECT count(*) FROM atualizacoes '
        'WHERE hash_pedido = ? AND hash_itens = ?',
        [hash_pedido, hash_itens],
    ).fetchone()[0]
    if repetida:
        raise AtualizacaoRepetidaError(
            'Este par de planilhas já foi aplicado à base.'
        )


def _hash_anterior(base) -> str:
    linha = base.execute(
        'SELECT hash_dados FROM atualizacoes ORDER BY aplicada_em DESC LIMIT 1'
    ).fetchone()
    return linha[0] if linha else HASH_INICIAL


def _validar_e_consolidar(base, pedidos: Path, itens: Path) -> dict:
    """Linhas novas por tabela, calculadas fora da base."""
    mem = duckdb.connect()
    try:
        mem.execute('INSTALL excel; LOAD excel')
        _carregar_bruto(mem, 'pedido', pedidos)
        _carregar_bruto(mem, 'item_pedido', itens)
        mem.execute(
            'CREATE TABLE bruto_sku (linha BIGINT, A VARCHAR, B VARCHAR)'
        )
        mem.executemany(
            'INSERT INTO bruto_sku VALUES (?, ?, ?)',
            [
                (i, sku, str(valor))
                for i, (sku, valor) in enumerate(
                    base.execute(
                        'SELECT sku, valor_unitario FROM sku ORDER BY sku'
                    ).fetchall(),
                    start=1,
                )
            ],
        )
        _recusar_pedidos_existentes(base, mem)
        _validar(mem)
        _consolidar(mem)
        return {
            tabela: mem.execute(f'SELECT * FROM {tabela}').fetchall()
            for tabela in _TABELAS_NOVAS
        }
    finally:
        mem.close()


def _recusar_pedidos_existentes(base, mem) -> None:
    existentes = {
        i for (i,) in base.execute('SELECT id_pedido FROM pedido').fetchall()
    }
    problemas = [
        f'PEDIDO linha {linha}: ID_PEDIDO {valor!r} já existe na base.'
        for linha, valor in mem.execute(
            'SELECT linha, B FROM bruto_pedido '
            'WHERE try_cast(B AS BIGINT) IS NOT NULL ORDER BY linha'
        ).fetchall()
        if int(valor) in existentes
    ]
    if problemas:
        exibidos = problemas[:MAX_MENSAGENS]
        if len(problemas) > MAX_MENSAGENS:
            exibidos.append(f'... e mais {len(problemas) - MAX_MENSAGENS}.')
        raise DadosInvalidosError(
            f'{len(problemas)} problema(s) nas planilhas:\n'
            + '\n'.join(exibidos)
        )


def _acrescentar(base, novos: dict) -> None:
    for tabela in _TABELAS_NOVAS:
        linhas = novos[tabela]
        if not linhas:
            continue
        marcas = ', '.join('?' for _ in linhas[0])
        base.executemany(f'INSERT INTO {tabela} VALUES ({marcas})', linhas)


def _guardar_copias(
    cfg: Settings, hash_dados: str, pedidos: Path, itens: Path
) -> None:
    destino = cfg.atualizacoes_dir / hash_dados
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pedidos, destino / 'pedido.xlsx')
    shutil.copy2(itens, destino / 'item_pedido.xlsx')
