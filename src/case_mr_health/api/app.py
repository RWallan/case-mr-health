"""Aplicação FastAPI: carrega os modelos na inicialização.

Nenhuma requisição de predição treina. O único caminho que reajusta modelos
é o envio de pedidos novos (ADR 0011).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import metadata

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from case_mr_health.api.erros import registrar_tratadores
from case_mr_health.api.historico import Historico
from case_mr_health.api.modelos import carregar_modelos
from case_mr_health.api.rotas import (
    atualizacao,
    changelog,
    consultas,
    predicao,
    recomendacoes,
)
from case_mr_health.api.servicos.atualizacao import GerenteAtualizacoes
from case_mr_health.config import Settings

ROTEADORES = (
    predicao.router,
    changelog.router,
    consultas.router,
    recomendacoes.router,
    atualizacao.router,
)


def criar_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or Settings()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        app.state.cfg = cfg
        app.state.modelos = carregar_modelos(cfg)
        app.state.historico = Historico(cfg.historico_db_path)
        app.state.atualizacoes = GerenteAtualizacoes(cfg, app.state.modelos)
        yield
        app.state.atualizacoes.fechar()
        app.state.historico.fechar()

    app = FastAPI(
        title='Previsão de demanda MR. HEALTH',
        version=metadata.version('case-mr-health'),
        description=(
            'Serve os modelos publicados no MLflow Model Registry, um por '
            'SKU e granularidade. As previsões são da rede. Nenhuma '
            'requisição de predição treina; o envio de pedidos novos '
            'reajusta os modelos (ADR 0011).'
        ),
        lifespan=ciclo_de_vida,
    )
    registrar_tratadores(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            'http://localhost:5173',
            'http://127.0.0.1:5173',
        ],
        allow_methods=['GET', 'POST'],
        allow_headers=['content-type'],
    )
    for roteador in ROTEADORES:
        app.include_router(roteador)
    return app
