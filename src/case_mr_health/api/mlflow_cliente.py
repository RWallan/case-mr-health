"""Integração com o MLflow: versão servida, artefato conferido e metadados.

O hash registrado pelo treino (ADR 0005) inclui `registered_model_meta`,
que o MLflow reescreve a cada download conforme a URI: com o nome do modelo
em `models:/<nome>/<versão>` e com `null` em `models:/<id>`, a URI do treino
e a `source` da versão. Por isso a conferência baixa pela `source`, numa
cópia: por nome o hash nunca bateria, e em lugar nenhum se altera o
armazenamento de artefatos.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
import mlflow.pyfunc
from mlflow import MlflowClient
from mlflow.entities import Run
from mlflow.entities.model_registry import ModelVersion
from mlflow.exceptions import MlflowException

from case_mr_health.config import Settings
from case_mr_health.treino import hash_artefato

ALIAS_CHAMPION = 'champion'
# O MLflow responde parâmetro inválido para alias que não existe.
_NAO_ENCONTRADO = ('RESOURCE_DOES_NOT_EXIST', 'INVALID_PARAMETER_VALUE')


class SemVersao(Exception):
    """A série não tem versão a servir."""


class ModeloRecusado(Exception):
    """Há versão, mas ela não pode ser servida."""


def conectar(cfg: Settings) -> MlflowClient:
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    return MlflowClient()


def resolver_versao(
    cliente: MlflowClient, nome: str, fixada: str | None
) -> ModelVersion:
    """Versão fixada ou `champion`; a fixada nunca recai no `champion`."""
    try:
        if fixada is not None:
            return cliente.get_model_version(nome, fixada)
        return cliente.get_model_version_by_alias(nome, ALIAS_CHAMPION)
    except MlflowException as erro:
        if erro.error_code not in _NAO_ENCONTRADO:
            raise
        alvo = (
            f'versão fixada {fixada}'
            if fixada is not None
            else f'alias {ALIAS_CHAMPION}'
        )
        raise SemVersao(f'{nome} sem {alvo}') from erro


def carregar_conferido(versao: ModelVersion):
    """Carrega o artefato depois de conferir o hash, sem desserializar antes.

    O que é conferido é exatamente o que é carregado (a cópia local).
    """
    esperado = versao.tags.get('hash_artefato')
    if not esperado:
        raise ModeloRecusado('versão sem a tag hash_artefato')
    with TemporaryDirectory() as temporario:
        local = Path(
            mlflow.artifacts.download_artifacts(
                versao.source, dst_path=temporario
            )
        )
        obtido = hash_artefato(local)
        if obtido != esperado:
            raise ModeloRecusado(
                f'hash divergente: esperado {esperado}, obtido {obtido}'
            )
        return mlflow.pyfunc.load_model(str(local))


def obter_run(cliente: MlflowClient, versao: ModelVersion) -> Run:
    return cliente.get_run(versao.run_id or versao.tags['run_id'])
