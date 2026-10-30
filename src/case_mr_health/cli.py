from pathlib import Path
from typing import Annotated

import uvicorn
from cyclopts import App, Parameter
from loguru import logger

from case_mr_health.api.app import criar_app
from case_mr_health.config import Settings
from case_mr_health.dados import DadosInvalidosError, preparar_dados
from case_mr_health.logs import configurar_logs
from case_mr_health.selecao import publicar_selecao
from case_mr_health.treino import ResumoTreino, treinar_serie, treinar_todas

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
    sku: Annotated[str | None, Parameter(name='--sku')] = None,
    granularidade: Annotated[
        str | None, Parameter(name='--granularidade')
    ] = None,
    todas: Annotated[bool, Parameter(name='--todas')] = False,
    seed: Annotated[int | None, Parameter(name='--seed')] = None,
) -> int:
    """Treina uma série ou todas (backtest, candidatos e registro no MLflow).

    Parameters
    ----------
    sku
        SKU da série (`item A` ou só `A`).
    granularidade
        `diaria` ou `semanal`.
    todas
        Treina as 8 séries numa mesma rodada, em vez de `--sku`.
    seed
        Seed (padrão: configuração ou a data local, YYYYMMDD).
    """
    cfg = Settings()
    configurar_logs(cfg.log_level)
    if todas == bool(sku and granularidade):
        logger.error('Use --todas ou --sku com --granularidade')
        return 1
    try:
        if todas:
            rodada, resumos = treinar_todas(cfg, seed)
            logger.info('Rodada {}', rodada)
        else:
            resumos = [treinar_serie(cfg, sku, granularidade, seed)]
    except ValueError as erro:
        logger.error('{}', erro)
        return 1
    for resumo in resumos:
        _relatar_runs(resumo)
    return 0


def _relatar_runs(resumo: ResumoTreino) -> None:
    for run in resumo.runs:
        logger.info(
            '{} {} {} {}: MAE {:.3f} MASE {:.3f} intervalo {} (versão {})',
            resumo.sku,
            resumo.granularidade,
            run.algoritmo,
            run.hiperparametros,
            run.medias['mae'],
            run.medias['mase'],
            run.intervalo_metodo,
            run.versao_modelo,
        )


@app.command(name='selecionar')
def selecionar(
    rodada: Annotated[str, Parameter(name='--rodada')],
    resumo_path: Annotated[Path, Parameter(name='--resumo-path')] = Path(
        'docs/relatorio/fase2/12-resumo.md'
    ),
) -> int:
    """Aplica o critério do #12 a uma rodada e publica a seleção.

    Parameters
    ----------
    rodada
        Identificador impresso pelo `treinar --todas`.
    resumo_path
        Resumo em markdown, por série.
    """
    cfg = Settings()
    configurar_logs(cfg.log_level)
    try:
        publicar_selecao(cfg, rodada, resumo_path)
    except ValueError as erro:
        logger.error('{}', erro)
        return 1
    return 0


@app.command(name='servir')
def servir(
    host: Annotated[str | None, Parameter(name='--host')] = None,
    porta: Annotated[int | None, Parameter(name='--porta')] = None,
) -> int:
    """Sobe a API com um único worker (ADR 0005).

    Parameters
    ----------
    host
        Endereço de escuta (padrão: configuração).
    porta
        Porta de escuta (padrão: configuração).
    """
    cfg = Settings()
    configurar_logs(cfg.log_level)
    uvicorn.run(
        criar_app(cfg),
        host=host or cfg.api_host,
        port=porta or cfg.api_port,
        workers=1,
    )
    return 0
