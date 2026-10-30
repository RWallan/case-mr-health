"""Reajuste do modelo servido na série estendida (#29, ADR 0011).

Reajusta o mesmo algoritmo, com os mesmos hiperparâmetros e a mesma seed da
versão servida, na série completa de `cfg.db_path`, recalibra os intervalos
e registra uma nova versão. Não há nova seleção, backtest nem OOT: a versão
nova não tem métrica fora da amostra. O alias `champion` passa para ela
quando a série serve o `champion`; uma versão fixada por configuração
continua fixada.
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb
import mlflow
import mlflow.pyfunc
import pandas as pd
from loguru import logger
from mlflow import MlflowClient
from mlflow.entities.model_registry import ModelVersion

from case_mr_health import algoritmos, intervalos
from case_mr_health.api import mlflow_cliente
from case_mr_health.atualizacao import ACESSO_BASE
from case_mr_health.config import Settings
from case_mr_health.intervalos import Calibracao
from case_mr_health.particoes import DIAS_POR_PERIODO
from case_mr_health.treino import (
    CAMINHO_MODELO,
    ModeloDemanda,
    aplicar_seed,
    config_intervalos,
    hash_artefato,
    horizonte_maximo,
    nome_modelo,
    preparar_mlflow,
    requisitos_pip,
    versao_codigo,
)

ORIGEM = 'atualizacao'
_SERIES = {
    'diaria': ('serie_diaria', 'data'),
    'semanal': ('serie_semanal', 'semana'),
}


@dataclass(frozen=True)
class Reajuste:
    sku: str
    granularidade: str
    versao_anterior: str
    versao_nova: str
    hash_artefato: str
    desenvolvimento_fim: date
    n_observacoes: int
    promovida: bool


@dataclass(frozen=True)
class _Ajuste:
    """Tudo o que o registro de uma versão reajustada precisa."""

    sku: str
    granularidade: str
    algoritmo: str
    hp: dict
    seed: int
    modelo: ModeloDemanda
    anterior: ModelVersion
    hash_dados: str
    serie: pd.Series
    fim: date


def carregar_serie_completa(
    cfg: Settings, sku: str, granularidade: str
) -> pd.Series:
    """Série inteira da base consolidada, incluindo o antigo OOT."""
    tabela, coluna = _SERIES[granularidade]
    with ACESSO_BASE, duckdb.connect(str(cfg.db_path), read_only=True) as con:
        linhas = con.execute(
            f'SELECT {coluna}, quantidade FROM {tabela} WHERE sku = ? '
            f'ORDER BY {coluna}',
            [sku],
        ).fetchall()
    if not linhas:
        raise ValueError(f'Série {sku}/{granularidade} sem dados')
    datas, quantidades = zip(*linhas, strict=True)
    return pd.Series(
        [float(q) for q in quantidades],
        index=pd.DatetimeIndex(datas),
        name='quantidade',
    )


def fim_do_periodo(serie: pd.Series, granularidade: str) -> date:
    """Último dia coberto: na semanal, o domingo da última semana."""
    ultimo = serie.index[-1].date()
    return ultimo + timedelta(days=DIAS_POR_PERIODO[granularidade] - 1)


def _calibrar(
    cfg: Settings,
    granularidade: str,
    versao_servida,
    y,
    seed: int,
) -> Calibracao:
    """Mesmo método de intervalo da versão servida, com a série nova."""
    config = config_intervalos(cfg)
    horizonte = horizonte_maximo(cfg, granularidade)
    if versao_servida.tags.get('intervalo_metodo') == intervalos.NATIVO:
        return intervalos.nativa(config.niveis, horizonte, y)
    algoritmo = versao_servida.tags['algoritmo']
    hp = json.loads(versao_servida.tags['hiperparametros'])
    return intervalos.calibrar(
        lambda: algoritmos.criar(algoritmo, hp, seed), y, horizonte, config
    )


def reajustar_serie(
    cfg: Settings, sku: str, granularidade: str, hash_dados: str
) -> Reajuste:
    """Registra a versão reajustada; falha sem alterar a versão servida."""
    cliente = mlflow_cliente.conectar(cfg)
    nome = nome_modelo(sku, granularidade)
    fixada = cfg.modelos_fixados.get(nome)
    anterior = mlflow_cliente.resolver_versao(cliente, nome, fixada)
    algoritmo = anterior.tags['algoritmo']
    hp = json.loads(anterior.tags['hiperparametros'])
    seed = int(cliente.get_run(anterior.run_id).data.params['seed'])
    serie = carregar_serie_completa(cfg, sku, granularidade)
    y = serie.to_numpy(dtype=float)

    aplicar_seed(seed)
    modelo = algoritmos.criar(algoritmo, hp, seed).ajustar(y)
    calibracao = _calibrar(cfg, granularidade, anterior, y, seed)
    fim = fim_do_periodo(serie, granularidade)
    versao_nova, hash_modelo = _registrar(
        cfg,
        cliente,
        _Ajuste(
            sku,
            granularidade,
            algoritmo,
            hp,
            seed,
            ModeloDemanda(modelo, calibracao),
            anterior,
            hash_dados,
            serie,
            fim,
        ),
    )
    promovida = fixada is None
    if promovida:
        cliente.set_registered_model_alias(
            nome, mlflow_cliente.ALIAS_CHAMPION, versao_nova
        )
    logger.info(
        '{}: versão {} reajustada de {} (champion: {})',
        nome,
        versao_nova,
        anterior.version,
        promovida,
    )
    return Reajuste(
        sku,
        granularidade,
        str(anterior.version),
        versao_nova,
        hash_modelo,
        fim,
        len(serie),
        promovida,
    )


def _registrar(
    cfg: Settings, cliente: MlflowClient, a: _Ajuste
) -> tuple[str, str]:
    nome = nome_modelo(a.sku, a.granularidade)
    calibracao = a.modelo.calibracao
    with mlflow.start_run(
        experiment_id=preparar_mlflow(cfg, a.granularidade),
        run_name=f'{ORIGEM}-{a.algoritmo}-{a.hash_dados[:8]}',
    ) as run:
        mlflow.set_tags({
            'sku': a.sku,
            'granularidade': a.granularidade,
            'algoritmo': a.algoritmo,
            'papel': ORIGEM,
            'origem': ORIGEM,
            'versao_anterior': str(a.anterior.version),
            'hash_dados': a.hash_dados,
        })
        mlflow.log_params({f'hp.{k}': v for k, v in a.hp.items()})
        mlflow.log_params({
            'seed': a.seed,
            'n_observacoes': len(a.serie),
            'desenvolvimento_inicio': a.serie.index[0].date(),
            'desenvolvimento_fim': a.fim,
            **{f'codigo.{k}': v for k, v in versao_codigo().items()},
        })
        info = mlflow.pyfunc.log_model(
            name=CAMINHO_MODELO,
            python_model=a.modelo,
            registered_model_name=nome,
            pip_requirements=requisitos_pip(a.modelo.previsor),
        )
        artefato = Path(mlflow.artifacts.download_artifacts(info.model_uri))
        hash_modelo = hash_artefato(artefato)
        mlflow.set_tag('hash_artefato', hash_modelo)
    versao = str(info.registered_model_version)
    for chave, valor in {
        'hash_artefato': hash_modelo,
        'algoritmo': a.algoritmo,
        'hiperparametros': json.dumps(a.hp, default=str),
        'run_id': run.info.run_id,
        'intervalo_metodo': calibracao.metodo,
        'intervalo_niveis': json.dumps(calibracao.niveis),
        'intervalo_horizonte': str(calibracao.horizonte),
        'origem': ORIGEM,
        'versao_anterior': str(a.anterior.version),
        'hash_dados': a.hash_dados,
    }.items():
        cliente.set_model_version_tag(nome, versao, chave, valor)
    return versao, hash_modelo
