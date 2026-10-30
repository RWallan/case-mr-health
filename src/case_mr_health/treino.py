"""Treino de uma série: backtest, métricas e registro no MLflow (#7).

Para cada candidato da tabela do #6 que tenha implementação em
`algoritmos.ALGORITMOS`, e para cada combinação de hiperparâmetros, abre
uma execução (run) no experimento da granularidade, registra o backtest e
o modelo ajustado com todo o desenvolvimento como uma versão de
`demanda-<sku>-<granularidade>` (ADR 0005). A escolha da versão que serve
a série é do #12/#13: aqui nenhum modelo é selecionado.
"""

import hashlib
import json
import random
import subprocess
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from zoneinfo import ZoneInfo

import mlflow
import mlflow.pyfunc
import numpy as np
import pandas as pd
from loguru import logger
from mlflow import MlflowClient

from case_mr_health import algoritmos, confianca, metricas
from case_mr_health.backtest import ResultadoBacktest, rodar_backtest
from case_mr_health.candidatos import SKUS, candidatos
from case_mr_health.config import Settings
from case_mr_health.particoes import (
    GRANULARIDADES,
    Particao,
    abrir_desenvolvimento,
    carregar_particoes,
)

PREFIXO_EXPERIMENTO = 'demanda'
CAMINHO_MODELO = 'modelo'
_COLUNA_DATA = {
    'diaria': ('serie_diaria', 'data'),
    'semanal': (
        'serie_semanal',
        'semana',
    ),
}


@dataclass(frozen=True)
class Contexto:
    """O que é comum a todos os runs de uma série."""

    cfg: Settings
    experimento_id: str
    serie: pd.Series
    particao: Particao
    seed: int
    codigo: dict[str, str]


@dataclass(frozen=True)
class ResumoRun:
    run_id: str
    algoritmo: str
    papel: str
    hiperparametros: dict
    medias: dict[str, float]
    versao_modelo: str
    hash_artefato: str


@dataclass(frozen=True)
class ResumoTreino:
    sku: str
    granularidade: str
    seed: int
    runs: tuple[ResumoRun, ...]
    sem_implementacao: tuple[str, ...]


def nome_modelo(sku: str, granularidade: str) -> str:
    """`demanda-<sku>-<granularidade>`, SKU em minúsculas e sem espaço."""
    slug = sku.lower().replace(' ', '-')
    return f'{PREFIXO_EXPERIMENTO}-{slug}-{granularidade}'


def nome_experimento(granularidade: str) -> str:
    return f'{PREFIXO_EXPERIMENTO}-{granularidade}'


def normalizar_sku(sku: str) -> str:
    """Aceita `item A` ou só a letra (`A`)."""
    letra = sku.strip().upper().removeprefix('ITEM').strip()
    candidato = f'item {letra}'
    if candidato not in SKUS:
        raise ValueError(f'SKU desconhecido: {sku}; use um de {SKUS}')
    return candidato


def seed_padrao(cfg: Settings, agora: datetime | None = None) -> int:
    """Seed efetiva: a configurada ou a data local de hoje, `YYYYMMDD`."""
    if cfg.seed is not None:
        return cfg.seed
    fuso = ZoneInfo(cfg.fuso_horario)
    agora = agora.astimezone(fuso) if agora else datetime.now(fuso)
    return int(agora.strftime('%Y%m%d'))


def aplicar_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)  # noqa: NPY002


def carregar_serie(cfg: Settings, sku: str, granularidade: str) -> pd.Series:
    """Série da visão de desenvolvimento (o OOT não está nesse arquivo)."""
    tabela, coluna = _COLUNA_DATA[granularidade]
    con = abrir_desenvolvimento(cfg)
    try:
        linhas = con.execute(
            f'SELECT {coluna}, quantidade FROM {tabela} WHERE sku = ? '
            f'ORDER BY {coluna}',
            [sku],
        ).fetchall()
    finally:
        con.close()
    if not linhas:
        raise ValueError(f'Série {sku}/{granularidade} sem dados')
    datas, quantidades = zip(*linhas, strict=True)
    return pd.Series(
        [float(q) for q in quantidades],
        index=pd.DatetimeIndex(datas),
        name='quantidade',
    )


def versao_codigo() -> dict[str, str]:
    """Versão do pacote e, quando há git, o commit e se a árvore está suja."""
    info = {'pacote': metadata.version('case-mr-health')}
    try:
        info['commit'] = _git('rev-parse', 'HEAD')
        info['arvore_suja'] = str(bool(_git('status', '--porcelain')))
    except OSError, subprocess.CalledProcessError:
        info['commit'] = 'desconhecido'
    return info


def _git(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        ['git', *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def hash_artefato(diretorio: Path) -> str:
    """SHA-256 dos arquivos do diretório (caminho relativo + conteúdo)."""
    resumo = hashlib.sha256()
    for arquivo in sorted(p for p in diretorio.rglob('*') if p.is_file()):
        resumo.update(arquivo.relative_to(diretorio).as_posix().encode())
        resumo.update(arquivo.read_bytes())
    return resumo.hexdigest()


class ModeloDemanda(mlflow.pyfunc.PythonModel):
    """Modelo servível: recebe `horizonte`, devolve previsão não negativa."""

    def __init__(self, previsor: algoritmos.Previsor):
        self.previsor = previsor

    def predict(self, context, model_input, params=None):
        horizonte = int(model_input['horizonte'].iloc[0])
        return np.clip(self.previsor.prever(horizonte), 0, None)


def _preparar_mlflow(cfg: Settings, granularidade: str) -> str:
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    cfg.mlflow_artifact_dir.mkdir(parents=True, exist_ok=True)
    nome = nome_experimento(granularidade)
    experimento = mlflow.get_experiment_by_name(nome)
    if experimento is not None:
        return experimento.experiment_id
    return mlflow.create_experiment(
        nome, artifact_location=cfg.mlflow_artifact_dir.resolve().as_uri()
    )


def treinar_serie(
    cfg: Settings,
    sku: str,
    granularidade: str,
    seed: int | None = None,
) -> ResumoTreino:
    """Treina todos os candidatos implementados de uma série."""
    if granularidade not in GRANULARIDADES:
        raise ValueError(f'granularidade desconhecida: {granularidade}')
    sku = normalizar_sku(sku)
    seed = seed if seed is not None else seed_padrao(cfg)
    aplicar_seed(seed)
    contexto = Contexto(
        cfg,
        _preparar_mlflow(cfg, granularidade),
        carregar_serie(cfg, sku, granularidade),
        _particao(cfg, sku, granularidade),
        seed,
        versao_codigo(),
    )

    runs, pendentes = [], []
    for candidato in candidatos(sku, granularidade):
        if not candidato.entra:
            continue
        if candidato.algoritmo not in algoritmos.ALGORITMOS:
            pendentes.append(candidato.algoritmo)
            continue
        for hiperparametros in candidato.combinacoes():
            runs.append(
                _treinar_candidato(
                    contexto,
                    candidato.algoritmo,
                    candidato.papel,
                    hiperparametros,
                )
            )
    if pendentes:
        logger.warning(
            '{}/{}: sem implementação, não treinados: {}',
            sku,
            granularidade,
            ', '.join(pendentes),
        )
    return ResumoTreino(
        sku, granularidade, seed, tuple(runs), tuple(pendentes)
    )


def _particao(cfg: Settings, sku: str, granularidade: str) -> Particao:
    for p in carregar_particoes(cfg):
        if (p.sku, p.granularidade) == (sku, granularidade):
            return p
    raise ValueError(f'Série {sku}/{granularidade} sem partição')


def _treinar_candidato(
    ctx: Contexto, algoritmo: str, papel: str, hiperparametros: dict
) -> ResumoRun:
    particao, seed = ctx.particao, ctx.seed
    aplicar_seed(seed)
    resultado = rodar_backtest(
        ctx.serie, particao, algoritmo, hiperparametros, seed
    )
    modelo_final = algoritmos.criar(algoritmo, hiperparametros, seed).ajustar(
        ctx.serie.to_numpy(dtype=float)
    )
    nome = nome_modelo(particao.sku, particao.granularidade)
    with mlflow.start_run(
        experiment_id=ctx.experimento_id,
        run_name=f'{algoritmo}-{json.dumps(hiperparametros, default=str)}',
    ) as run:
        mlflow.set_tags({
            'sku': particao.sku,
            'granularidade': particao.granularidade,
            'algoritmo': algoritmo,
            'papel': papel,
        })
        _registrar_parametros(ctx, hiperparametros)
        _registrar_metricas(resultado)
        info = mlflow.pyfunc.log_model(
            name=CAMINHO_MODELO,
            python_model=ModeloDemanda(modelo_final),
            registered_model_name=nome,
            pip_requirements=['numpy'],
        )
        artefato = Path(mlflow.artifacts.download_artifacts(info.model_uri))
        hash_modelo = hash_artefato(artefato)
        mlflow.set_tag('hash_artefato', hash_modelo)
        MlflowClient().set_model_version_tag(
            nome, info.registered_model_version, 'hash_artefato', hash_modelo
        )
        for chave, valor in {
            'algoritmo': algoritmo,
            'hiperparametros': json.dumps(hiperparametros, default=str),
            'run_id': run.info.run_id,
        }.items():
            MlflowClient().set_model_version_tag(
                nome, info.registered_model_version, chave, valor
            )
        confianca.registrar(
            nome, info.registered_model_version, resultado, ctx.cfg
        )
    return ResumoRun(
        run.info.run_id,
        algoritmo,
        papel,
        hiperparametros,
        resultado.medias,
        str(info.registered_model_version),
        hash_modelo,
    )


def _registrar_parametros(ctx: Contexto, hiperparametros: dict) -> None:
    particao = ctx.particao
    mlflow.log_params({f'hp.{k}': v for k, v in hiperparametros.items()})
    mlflow.log_params({
        'seed': ctx.seed,
        'n_observacoes': len(ctx.serie),
        'n_folds': len(particao.folds),
        'desenvolvimento_inicio': particao.desenvolvimento_inicio,
        'desenvolvimento_fim': particao.desenvolvimento_fim,
        'oot_inicio': particao.oot_inicio,
        'oot_fim': particao.oot_fim,
        **{f'codigo.{k}': v for k, v in ctx.codigo.items()},
    })
    for i, fold in enumerate(particao.folds, start=1):
        mlflow.log_params({
            f'fold_{i}.treino': f'{fold.treino_inicio}/{fold.treino_fim}',
            f'fold_{i}.teste': f'{fold.teste_inicio}/{fold.teste_fim}',
        })
    mlflow.log_dict(json.loads(ctx.cfg.model_dump_json()), 'config.json')


def _registrar_metricas(resultado: ResultadoBacktest) -> None:
    indefinidas = []
    for m in metricas.METRICAS:
        for r in resultado.folds:
            _metrica(f'{m}_fold', r.metricas[m], r.fold, indefinidas)
        _metrica(m, resultado.medias[m], None, indefinidas)
        valores = [r.metricas[m] for r in resultado.folds]
        _metrica(
            f'{m}_dp',
            float(np.std(valores, ddof=1))
            if len(valores) > 1
            else float('nan'),
            None,
            indefinidas,
        )
    for variante, medias in resultado.sensibilidade.items():
        for m, valor in medias.items():
            _metrica(f'sens_{variante}_{m}', valor, None, indefinidas)
    if indefinidas:
        mlflow.set_tag(
            'metricas_indefinidas', ','.join(sorted(set(indefinidas)))
        )


def _metrica(chave, valor, passo, indefinidas) -> None:
    if np.isnan(valor):
        indefinidas.append(chave)
        return
    mlflow.log_metric(chave, valor, step=passo)
