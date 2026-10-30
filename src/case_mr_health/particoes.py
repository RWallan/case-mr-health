from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb
from loguru import logger

from case_mr_health.config import Settings

GRANULARIDADES = ('diaria', 'semanal')
DIAS_POR_PERIODO = {'diaria': 1, 'semanal': 7}


@dataclass(frozen=True)
class Fold:
    treino_inicio: date
    treino_fim: date
    teste_inicio: date
    teste_fim: date


@dataclass(frozen=True)
class Particao:
    """Partições de uma série; datas inclusivas (semana: segunda a domingo)."""

    sku: str
    granularidade: str
    desenvolvimento_inicio: date
    desenvolvimento_fim: date
    oot_inicio: date
    oot_fim: date
    folds: tuple[Fold, ...]


def _tamanhos(cfg: Settings, granularidade: str) -> tuple[int, int, int]:
    """Períodos de OOT, de fold e de treino mínimo."""
    if granularidade == 'diaria':
        return (
            cfg.oot_diaria_dias,
            cfg.fold_diaria_dias,
            cfg.treino_minimo_diaria_dias,
        )
    return (
        cfg.oot_semanal_semanas,
        cfg.fold_semanal_semanas,
        cfg.treino_minimo_semanal_semanas,
    )


def particionar(
    sku: str, granularidade: str, periodos: list[date], cfg: Settings
) -> Particao:
    """Define o OOT final e os folds de origem móvel (janela expansiva).

    `periodos` são as datas de início dos períodos consecutivos da série.
    Só usa as datas, nunca os valores de venda.
    """
    oot_n, fold_n, treino_min = _tamanhos(cfg, granularidade)
    periodos = sorted(periodos)
    dev = periodos[: len(periodos) - oot_n]
    if len(dev) <= treino_min or oot_n <= 0:
        raise ValueError(
            f'Série {sku}/{granularidade} sem períodos suficientes: '
            f'{len(periodos)} períodos, OOT {oot_n}, treino mínimo '
            f'{treino_min}.'
        )
    ultimo_dia = timedelta(days=DIAS_POR_PERIODO[granularidade] - 1)
    folds = tuple(
        Fold(
            treino_inicio=dev[0],
            treino_fim=dev[t - 1] + ultimo_dia,
            teste_inicio=dev[t],
            teste_fim=dev[t + fold_n - 1] + ultimo_dia,
        )
        for t in range(treino_min, len(dev) - fold_n + 1, fold_n)
    )
    return Particao(
        sku=sku,
        granularidade=granularidade,
        desenvolvimento_inicio=dev[0],
        desenvolvimento_fim=dev[-1] + ultimo_dia,
        oot_inicio=periodos[len(dev)],
        oot_fim=periodos[-1] + ultimo_dia,
        folds=folds,
    )


def separar_series(cfg: Settings) -> list[Particao]:
    """Separa fisicamente a visão de desenvolvimento e o OOT.

    Lê as séries de `cfg.db_path` e grava `cfg.desenvolvimento_db_path`
    (séries sem o OOT, `particao` e `fold`) e `cfg.oot_db_path` (só o
    OOT). A EDA, a seleção e o backtest abrem apenas o primeiro arquivo.
    """
    origem = duckdb.connect(str(cfg.db_path), read_only=True)
    try:
        periodos = {
            ('diaria', sku): [d for (d,) in datas]
            for sku, datas in _agrupar(
                origem, 'SELECT sku, data FROM serie_diaria'
            )
        }
        periodos |= {
            ('semanal', sku): [d for (d,) in datas]
            for sku, datas in _agrupar(
                origem, 'SELECT sku, semana FROM serie_semanal'
            )
        }
    finally:
        origem.close()

    particoes = [
        particionar(sku, gran, datas, cfg)
        for (gran, sku), datas in sorted(periodos.items())
    ]
    _gravar_desenvolvimento(cfg, particoes)
    _gravar_oot(cfg, particoes)
    logger.info(
        'Visão de desenvolvimento em {}; OOT selado em {}',
        cfg.desenvolvimento_db_path,
        cfg.oot_db_path,
    )
    return particoes


def _agrupar(con, sql: str) -> list[tuple[str, list[tuple]]]:
    por_sku: dict[str, list[tuple]] = {}
    for sku, dia in con.execute(sql).fetchall():
        por_sku.setdefault(sku, []).append((dia,))
    return list(por_sku.items())


def _recriar(caminho: Path) -> duckdb.DuckDBPyConnection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.unlink(missing_ok=True)
    return duckdb.connect(str(caminho))


def _gravar_desenvolvimento(cfg: Settings, particoes: list[Particao]) -> None:
    con = _recriar(cfg.desenvolvimento_db_path)
    try:
        con.execute(
            'CREATE TABLE particao (sku VARCHAR, granularidade VARCHAR, '
            'desenvolvimento_inicio DATE, desenvolvimento_fim DATE, '
            'oot_inicio DATE, oot_fim DATE)'
        )
        con.execute(
            'CREATE TABLE fold (sku VARCHAR, granularidade VARCHAR, '
            'fold INTEGER, treino_inicio DATE, treino_fim DATE, '
            'teste_inicio DATE, teste_fim DATE)'
        )
        for p in particoes:
            con.execute(
                'INSERT INTO particao VALUES (?, ?, ?, ?, ?, ?)',
                [
                    p.sku,
                    p.granularidade,
                    p.desenvolvimento_inicio,
                    p.desenvolvimento_fim,
                    p.oot_inicio,
                    p.oot_fim,
                ],
            )
            con.executemany(
                'INSERT INTO fold VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    [
                        p.sku,
                        p.granularidade,
                        i,
                        f.treino_inicio,
                        f.treino_fim,
                        f.teste_inicio,
                        f.teste_fim,
                    ]
                    for i, f in enumerate(p.folds, start=1)
                ],
            )
        con.execute(f"ATTACH '{cfg.db_path}' AS origem (READ_ONLY)")
        for tabela, coluna, gran in (
            ('serie_diaria', 'data', 'diaria'),
            ('serie_semanal', 'semana', 'semanal'),
        ):
            con.execute(
                f'CREATE TABLE {tabela} AS SELECT s.* '
                f'FROM origem.{tabela} s JOIN particao p '
                f"ON p.sku = s.sku AND p.granularidade = '{gran}' "
                f'WHERE s.{coluna} <= p.desenvolvimento_fim '
                f'ORDER BY s.sku, s.{coluna}'
            )
        con.execute('DETACH origem')
    finally:
        con.close()


def _gravar_oot(cfg: Settings, particoes: list[Particao]) -> None:
    con = _recriar(cfg.oot_db_path)
    try:
        con.execute(
            'CREATE TEMP TABLE limite (sku VARCHAR, granularidade VARCHAR, '
            'oot_inicio DATE)'
        )
        con.executemany(
            'INSERT INTO limite VALUES (?, ?, ?)',
            [[p.sku, p.granularidade, p.oot_inicio] for p in particoes],
        )
        con.execute(f"ATTACH '{cfg.db_path}' AS origem (READ_ONLY)")
        for tabela, coluna, gran in (
            ('serie_diaria', 'data', 'diaria'),
            ('serie_semanal', 'semana', 'semanal'),
        ):
            con.execute(
                f'CREATE TABLE {tabela} AS SELECT s.* '
                f'FROM origem.{tabela} s JOIN limite l '
                f"ON l.sku = s.sku AND l.granularidade = '{gran}' "
                f'WHERE s.{coluna} >= l.oot_inicio '
                f'ORDER BY s.sku, s.{coluna}'
            )
        con.execute('DETACH origem')
    finally:
        con.close()


def abrir_desenvolvimento(cfg: Settings) -> duckdb.DuckDBPyConnection:
    """Abre (somente leitura) a única visão permitida para a EDA e o treino."""
    return duckdb.connect(str(cfg.desenvolvimento_db_path), read_only=True)


def carregar_particoes(cfg: Settings) -> list[Particao]:
    """Lê as partições (só datas) registradas na visão de desenvolvimento."""
    con = abrir_desenvolvimento(cfg)
    try:
        folds: dict[tuple[str, str], list[Fold]] = {}
        for sku, gran, *datas in con.execute(
            'SELECT sku, granularidade, treino_inicio, treino_fim, '
            'teste_inicio, teste_fim FROM fold ORDER BY sku, '
            'granularidade, fold'
        ).fetchall():
            folds.setdefault((sku, gran), []).append(Fold(*datas))
        return [
            Particao(sku, gran, *datas, tuple(folds.get((sku, gran), ())))
            for sku, gran, *datas in con.execute(
                'SELECT sku, granularidade, desenvolvimento_inicio, '
                'desenvolvimento_fim, oot_inicio, oot_fim FROM particao '
                'ORDER BY granularidade, sku'
            ).fetchall()
        ]
    finally:
        con.close()
