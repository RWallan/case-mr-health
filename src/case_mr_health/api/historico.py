"""Histórico de previsões em DuckDB exclusivo do serviço (ADR 0005).

Uma conexão no processo, serializada por trava; por isso um único worker.
`data_geracao` é gravada em UTC, sem fuso: `TIMESTAMPTZ` exigiria `pytz` para
ser lido, e ele não é dependência do projeto.
"""

from collections.abc import Sequence
from dataclasses import astuple, dataclass, fields
from datetime import date, datetime
from pathlib import Path
from threading import Lock

import duckdb

from case_mr_health.api.erros import HistoricoIndisponivel

_CRIAR = """
CREATE TABLE IF NOT EXISTS previsoes (
    id_requisicao VARCHAR NOT NULL,
    sku VARCHAR NOT NULL,
    granularidade VARCHAR NOT NULL,
    data_geracao TIMESTAMP NOT NULL,
    data_referencia DATE NOT NULL,
    data_alvo DATE NOT NULL,
    versao_modelo VARCHAR NOT NULL,
    hash_artefato VARCHAR NOT NULL,
    quantidade_prevista DOUBLE NOT NULL,
    valor_unitario DOUBLE NOT NULL,
    valor_previsto DOUBLE NOT NULL,
    limite_inferior_80 DOUBLE,
    limite_superior_80 DOUBLE,
    limite_inferior_95 DOUBLE,
    limite_superior_95 DOUBLE,
    confianca VARCHAR,
    experimento_id VARCHAR NOT NULL,
    run_id VARCHAR NOT NULL,
    PRIMARY KEY (id_requisicao, data_alvo)
)
"""


@dataclass(frozen=True)
class LinhaHistorico:
    """Um período-alvo de uma previsão servida; ordem igual à da tabela."""

    id_requisicao: str
    sku: str
    granularidade: str
    data_geracao: datetime
    data_referencia: date
    data_alvo: date
    versao_modelo: str
    hash_artefato: str
    quantidade_prevista: float
    valor_unitario: float
    valor_previsto: float
    limite_inferior_80: float | None
    limite_superior_80: float | None
    limite_inferior_95: float | None
    limite_superior_95: float | None
    confianca: str | None
    experimento_id: str
    run_id: str


_COLUNAS = ', '.join(f.name for f in fields(LinhaHistorico))
_MARCAS = ', '.join('?' for _ in fields(LinhaHistorico))


class Historico:
    def __init__(self, caminho: Path):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(caminho))
        self._con.execute(_CRIAR)
        self._trava = Lock()

    def registrar(self, linhas: Sequence[LinhaHistorico]) -> None:
        """Grava todos os períodos de uma requisição, ou nenhum."""
        try:
            with self._trava:
                self._gravar(linhas)
        except duckdb.Error as erro:
            raise HistoricoIndisponivel(
                'A previsão não foi servida porque não pôde ser registrada '
                'no histórico.'
            ) from erro

    def _gravar(self, linhas: Sequence[LinhaHistorico]) -> None:
        self._con.begin()
        try:
            self._con.executemany(
                f'INSERT INTO previsoes ({_COLUNAS}) VALUES ({_MARCAS})',
                [astuple(linha) for linha in linhas],
            )
            self._con.commit()
        except duckdb.Error:
            self._con.rollback()
            raise

    def fechar(self) -> None:
        with self._trava:
            self._con.close()
