"""Aplicação FastAPI: carrega os modelos na inicialização e nunca treina."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import metadata

from fastapi import FastAPI

from case_mr_health.api.erros import registrar_tratadores
from case_mr_health.api.historico import Historico
from case_mr_health.api.modelos import carregar_modelos
from case_mr_health.api.rotas import changelog, predicao
from case_mr_health.config import Settings

ROTEADORES = (predicao.router, changelog.router)


def criar_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or Settings()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        app.state.cfg = cfg
        app.state.modelos = carregar_modelos(cfg)
        app.state.historico = Historico(cfg.historico_db_path)
        yield
        app.state.historico.fechar()

    app = FastAPI(
        title='Previsão de demanda MR. HEALTH',
        version=metadata.version('case-mr-health'),
        description=(
            'Serve os modelos publicados no MLflow Model Registry, um por '
            'SKU e granularidade. As previsões são da rede. Nenhuma '
            'requisição dispara treino.'
        ),
        lifespan=ciclo_de_vida,
    )
    registrar_tratadores(app)
    for roteador in ROTEADORES:
        app.include_router(roteador)
    return app
