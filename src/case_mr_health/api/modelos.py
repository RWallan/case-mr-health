"""Carregamento dos modelos na inicialização; nunca treina (ADR 0005)."""

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from loguru import logger
from mlflow import MlflowClient

from case_mr_health.api import mlflow_cliente
from case_mr_health.api.erros import ModeloIndisponivel
from case_mr_health.api.mlflow_cliente import ModeloRecusado, SemVersao
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.particoes import GRANULARIDADES
from case_mr_health.treino import horizonte_maximo, nome_modelo

COLUNAS = (
    'previsao',
    'inferior_80',
    'superior_80',
    'inferior_95',
    'superior_95',
)


@dataclass(frozen=True)
class ModeloServido:
    """Uma versão conferida, com o que a resposta precisa dela."""

    sku: str
    granularidade: str
    nome: str
    versao: str
    hash_artefato: str
    run_id: str
    experimento_id: str
    desenvolvimento_fim: date
    confianca: str | None
    modelo: Any

    def prever(self, horizonte: int) -> pd.DataFrame:
        """Os próximos `horizonte` períodos após `desenvolvimento_fim`."""
        return self.modelo.predict(
            pd.DataFrame({'horizonte': [horizonte], 'intervalos': [True]})
        )


class CatalogoModelos:
    """Um modelo ou um motivo de indisponibilidade por série."""

    def __init__(
        self,
        modelos: dict[tuple[str, str], ModeloServido],
        indisponiveis: dict[tuple[str, str], str],
    ):
        self.modelos = modelos
        self.indisponiveis = indisponiveis

    def obter(self, sku: str, granularidade: str) -> ModeloServido:
        """Só a série pedida: nunca a outra granularidade do mesmo SKU."""
        modelo = self.modelos.get((sku, granularidade))
        if modelo is None:
            motivo = self.indisponiveis[sku, granularidade]
            raise ModeloIndisponivel(
                f'Sem modelo para {sku}/{granularidade}: {motivo}. A API não '
                'usa outro modelo nem treina um novo.'
            )
        return modelo


def carregar_modelos(cfg: Settings) -> CatalogoModelos:
    """Uma tentativa por série; a falha de uma não derruba a API."""
    cliente = mlflow_cliente.conectar(cfg)
    nomes = {
        nome_modelo(sku, granularidade)
        for sku in SKUS
        for granularidade in GRANULARIDADES
    }
    desconhecidos = sorted(set(cfg.modelos_fixados) - nomes)
    if desconhecidos:
        logger.warning('Modelos fixados desconhecidos: {}', desconhecidos)

    modelos, indisponiveis = {}, {}
    for sku in SKUS:
        for granularidade in GRANULARIDADES:
            serie = (sku, granularidade)
            try:
                modelos[serie] = _carregar_serie(
                    cfg, cliente, sku, granularidade
                )
                logger.info(
                    '{}/{}: versão {}',
                    sku,
                    granularidade,
                    modelos[serie].versao,
                )
            except SemVersao as erro:
                indisponiveis[serie] = str(erro)
                logger.warning('{}/{}: {}', sku, granularidade, erro)
            except ModeloRecusado as erro:
                indisponiveis[serie] = str(erro)
                logger.error('{}/{}: {}', sku, granularidade, erro)
            # O MLflow pode falhar de muitas formas (URI, banco, pickle), e
            # a falha de uma série vira indisponibilidade dela (#14).
            except Exception as erro:  # noqa: BLE001
                indisponiveis[serie] = 'falha ao carregar o modelo'
                logger.exception('{}/{}: {}', sku, granularidade, erro)
    return CatalogoModelos(modelos, indisponiveis)


def _carregar_serie(
    cfg: Settings, cliente: MlflowClient, sku: str, granularidade: str
) -> ModeloServido:
    nome = nome_modelo(sku, granularidade)
    versao = mlflow_cliente.resolver_versao(
        cliente, nome, cfg.modelos_fixados.get(nome)
    )
    run = mlflow_cliente.obter_run(cliente, versao)
    _conferir_serie(run.data.tags, sku, granularidade)
    if sku not in cfg.valores_unitarios:
        raise ModeloRecusado(f'{sku} sem valor unitário configurado')
    servido = ModeloServido(
        sku=sku,
        granularidade=granularidade,
        nome=nome,
        versao=str(versao.version),
        hash_artefato=versao.tags.get('hash_artefato', ''),
        run_id=run.info.run_id,
        experimento_id=run.info.experiment_id,
        desenvolvimento_fim=date.fromisoformat(
            run.data.params['desenvolvimento_fim']
        ),
        confianca=mlflow_cliente.ler_confianca(versao),
        modelo=mlflow_cliente.carregar_conferido(versao),
    )
    _conferir_contrato(servido, horizonte_maximo(cfg, granularidade))
    return servido


def _conferir_serie(tags: dict, sku: str, granularidade: str) -> None:
    """A versão registrada precisa ser mesmo da série pedida."""
    obtida = (tags.get('sku'), tags.get('granularidade'))
    if obtida != (sku, granularidade):
        raise ModeloRecusado(
            f'versão treinada para {obtida}, não para {(sku, granularidade)}'
        )


def _conferir_contrato(servido: ModeloServido, horizonte: int) -> None:
    """Versão sem os limites de 80% e 95% até o máximo não é servível."""
    try:
        previsto = servido.prever(horizonte)
    except ValueError as erro:
        raise ModeloRecusado(f'previsão recusada: {erro}') from erro
    faltando = sorted(set(COLUNAS) - set(previsto.columns))
    if faltando or len(previsto) != horizonte:
        raise ModeloRecusado(
            f'saída fora do contrato: faltam {faltando}, '
            f'{len(previsto)} períodos em vez de {horizonte}'
        )
