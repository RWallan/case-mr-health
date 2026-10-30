"""Implementação das consultas e da exportação XLSX (#16, #22)."""

from datetime import UTC, datetime
from io import BytesIO

import duckdb
from loguru import logger
from mlflow.exceptions import MlflowException
from openpyxl import Workbook

from case_mr_health.api.erros import (
    HistoricoIndisponivel,
    ModeloIndisponivel,
)
from case_mr_health.api.historico import LinhaHistorico
from case_mr_health.api.mlflow_cliente import conectar
from case_mr_health.api.schemas.consultas import (
    PontoHistorico,
    VersaoDisponivel,
)
from case_mr_health.atualizacao import ACESSO_BASE
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.particoes import GRANULARIDADES
from case_mr_health.treino import nome_modelo

_COLUNAS_XLSX = (
    ('sku', 'SKU'),
    ('granularidade', 'Granularidade'),
    ('data_alvo', 'Período-alvo'),
    ('quantidade_prevista', 'Quantidade prevista'),
    ('valor_unitario', 'Valor unitário'),
    ('valor_previsto', 'Valor previsto'),
    ('limite_inferior_80', 'Limite inferior 80%'),
    ('limite_superior_80', 'Limite superior 80%'),
    ('limite_inferior_95', 'Limite inferior 95%'),
    ('limite_superior_95', 'Limite superior 95%'),
    ('recomendacao', 'Recomendação'),
    ('versao_modelo', 'Versão do modelo'),
    ('hash_artefato', 'Hash do artefato'),
    ('data_geracao', 'Data de geração'),
    ('id_requisicao', 'ID da requisição'),
)
_SERIE = {
    'diaria': ('serie_diaria', 'data', True),
    'semanal': ('serie_semanal', 'semana', False),
}


def gerar_xlsx(linhas: list[LinhaHistorico]) -> bytes:
    """Gera uma planilha com o histórico, sem colunas removidas do produto."""
    livro = Workbook()
    aba = livro.active
    aba.title = 'Previsões'
    aba.append([rotulo for _, rotulo in _COLUNAS_XLSX])
    for linha in linhas:
        aba.append([getattr(linha, chave) for chave, _ in _COLUNAS_XLSX])
    aba.freeze_panes = 'A2'
    aba.auto_filter.ref = aba.dimensions
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def _aliases_por_versao(modelo) -> dict[str, list[str]]:
    por_versao: dict[str, list[str]] = {}
    for alias, versao in modelo.aliases.items():
        por_versao.setdefault(str(versao), []).append(alias)
    return por_versao


def _versoes_da_serie(
    cliente, sku: str, granularidade: str
) -> list[VersaoDisponivel]:
    nome = nome_modelo(sku, granularidade)
    encontradas = cliente.search_model_versions(f"name = '{nome}'")
    if not encontradas:
        return []
    # A busca de versões não devolve aliases; eles vêm do modelo.
    por_versao = _aliases_por_versao(cliente.get_registered_model(nome))
    versoes = []
    for versao in encontradas:
        aliases = sorted(por_versao.get(str(versao.version), ()))
        versoes.append(
            VersaoDisponivel(
                sku=sku,
                granularidade=granularidade,
                versao=str(versao.version),
                aliases=aliases,
                champion='champion' in aliases,
                algoritmo=versao.tags.get('algoritmo'),
                origem=versao.tags.get('origem', 'treino'),
                versao_anterior=versao.tags.get('versao_anterior'),
                hash_artefato=versao.tags.get('hash_artefato'),
                run_id=versao.run_id or versao.tags.get('run_id'),
                criada_em=datetime.fromtimestamp(
                    versao.creation_timestamp / 1000, tz=UTC
                ),
            )
        )
    return versoes


def listar_modelos(cfg: Settings) -> list[VersaoDisponivel]:
    """Lista metadados das versões, sem carregar os artefatos."""
    try:
        cliente = conectar(cfg)
        versoes = [
            versao
            for sku in SKUS
            for granularidade in GRANULARIDADES
            for versao in _versoes_da_serie(cliente, sku, granularidade)
        ]
    except (MlflowException, OSError, ValueError, TypeError) as erro:
        logger.exception('Falha ao consultar versões no Registry: {}', erro)
        raise ModeloIndisponivel(
            'O catálogo de modelos não está disponível.'
        ) from erro
    return sorted(
        versoes, key=lambda v: (v.sku, v.granularidade, -int(v.versao))
    )


def carregar_serie(
    cfg: Settings, sku: str, granularidade: str
) -> list[PontoHistorico]:
    """Série completa da base consolidada, com os pedidos já ingeridos.

    Desde o ADR 0011 o antigo OOT é histórico (a avaliação final já foi
    consumida), então a série vem de `db_path`, não da visão de
    desenvolvimento.
    """
    tabela, coluna, tem_imputado = _SERIE[granularidade]
    try:
        with (
            ACESSO_BASE,
            duckdb.connect(str(cfg.db_path), read_only=True) as con,
        ):
            if tem_imputado:
                linhas = con.execute(
                    f'SELECT {coluna}, quantidade, imputado FROM {tabela} '
                    f'WHERE sku = ? ORDER BY {coluna}',
                    [sku],
                ).fetchall()
            else:
                linhas = con.execute(
                    f'SELECT {coluna}, quantidade FROM {tabela} '
                    f'WHERE sku = ? ORDER BY {coluna}',
                    [sku],
                ).fetchall()
    except duckdb.Error as erro:
        logger.exception(
            'Falha ao consultar a série de desenvolvimento: {}', erro
        )
        raise HistoricoIndisponivel(
            'A série de vendas não está disponível.'
        ) from erro
    return [
        PontoHistorico(
            data=row[0],
            quantidade=float(row[1]),
            imputado=bool(row[2]) if tem_imputado else False,
        )
        for row in linhas
    ]
