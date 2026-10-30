from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from loguru import logger

from case_mr_health.config import Settings
from case_mr_health.dados import DadosInvalidosError, preparar_dados
from case_mr_health.logs import configurar_logs
from case_mr_health.treino import treinar_serie

app = App(name='case-mr-health', help='Previsão de demanda da MR. HEALTH.')


@app.command(name='preparar-dados')
def preparar(
    raw_dir: Annotated[Path | None, Parameter(name='--raw-dir')] = None,
    db_path: Annotated[Path | None, Parameter(name='--db-path')] = None,
    relatorio_path: Annotated[
        Path | None, Parameter(name='--relatorio-path')
    ] = None,
    desenvolvimento_db_path: Annotated[
        Path | None, Parameter(name='--desenvolvimento-db-path')
    ] = None,
    oot_db_path: Annotated[
        Path | None, Parameter(name='--oot-db-path')
    ] = None,
) -> int:
    """Consolida as planilhas, gera o relatório e separa o OOT.

    Parameters
    ----------
    raw_dir
        Diretório das planilhas brutas (padrão: configuração).
    db_path
        Arquivo DuckDB de saída (padrão: configuração).
    relatorio_path
        Relatório de qualidade em markdown (padrão: configuração).
    desenvolvimento_db_path
        DuckDB da visão de desenvolvimento, sem o OOT (padrão: configuração).
    oot_db_path
        DuckDB do OOT selado (padrão: configuração).
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
                        'desenvolvimento_db_path': desenvolvimento_db_path,
                        'oot_db_path': oot_db_path,
                    }.items()
                    if v is not None
                }
            )
        )
    except DadosInvalidosError as erro:
        logger.error('{}', erro)
        return 1
    return 0


@app.command(name='treinar')
def treinar(
    sku: Annotated[str, Parameter(name='--sku')],
    granularidade: Annotated[str, Parameter(name='--granularidade')],
    seed: Annotated[int | None, Parameter(name='--seed')] = None,
) -> int:
    """Treina uma série (backtest, baselines e registro no MLflow).

    Parameters
    ----------
    sku
        SKU da série (`item A` ou só `A`).
    granularidade
        `diaria` ou `semanal`.
    seed
        Seed (padrão: configuração ou a data local, YYYYMMDD).
    """
    cfg = Settings()
    configurar_logs(cfg.log_level)
    try:
        resumo = treinar_serie(cfg, sku, granularidade, seed)
    except ValueError as erro:
        logger.error('{}', erro)
        return 1
    for run in resumo.runs:
        logger.info(
            '{} {} {}: MAE {:.3f} MASE {:.3f} (versão {})',
            resumo.sku,
            run.algoritmo,
            run.hiperparametros,
            run.medias['mae'],
            run.medias['mase'],
            run.versao_modelo,
        )
    return 0
