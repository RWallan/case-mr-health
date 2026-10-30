from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from loguru import logger

from case_mr_health.config import Settings
from case_mr_health.dados import DadosInvalidosError, preparar_dados
from case_mr_health.logs import configurar_logs

app = App(name='case-mr-health', help='Previsão de demanda da MR. HEALTH.')


@app.command(name='preparar-dados')
def preparar(
    raw_dir: Annotated[Path | None, Parameter(name='--raw-dir')] = None,
    db_path: Annotated[Path | None, Parameter(name='--db-path')] = None,
    relatorio_path: Annotated[
        Path | None, Parameter(name='--relatorio-path')
    ] = None,
) -> int:
    """Consolida as planilhas brutas em DuckDB e gera o relatório de qualidade.

    Parameters
    ----------
    raw_dir
        Diretório das planilhas brutas (padrão: configuração).
    db_path
        Arquivo DuckDB de saída (padrão: configuração).
    relatorio_path
        Relatório de qualidade em markdown (padrão: configuração).
    """
    cfg = Settings()
    configurar_logs(cfg.log_level)
    try:
        preparar_dados(
            cfg.model_copy(
                update={
                    k: v
                    for k, v in {
                        'raw_dir': raw_dir,
                        'db_path': db_path,
                        'relatorio_path': relatorio_path,
                    }.items()
                    if v is not None
                }
            )
        )
    except DadosInvalidosError as erro:
        logger.error('{}', erro)
        return 1
    return 0
