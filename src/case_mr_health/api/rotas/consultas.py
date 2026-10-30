"""Consultas do histórico, versões do Registry e série de desenvolvimento."""

from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from case_mr_health.api.erros import (
    SkuInexistente,
)
from case_mr_health.api.schemas.consultas import (
    ItemPrevisaoHistorica,
    RespostaHistorico,
    RespostaModelos,
    SerieHistorica,
)
from case_mr_health.api.schemas.erros import ErroResposta
from case_mr_health.api.servicos import consultas
from case_mr_health.candidatos import SKUS
from case_mr_health.treino import normalizar_sku

router = APIRouter(tags=['Consultas'])
_MIME_XLSX = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


def _erro(descricao: str, codigo: str, mensagem: str) -> dict:
    return {
        'model': ErroResposta,
        'description': descricao,
        'content': {
            'application/json': {
                'example': {
                    'codigo': codigo,
                    'mensagem': mensagem,
                    'detalhes': [],
                }
            }
        },
    }


@router.get(
    '/previsoes',
    response_model=RespostaHistorico,
    summary='Consulta previsões já servidas',
    responses={
        503: _erro(
            'Histórico indisponível.',
            'historico_indisponivel',
            'O histórico de previsões não está disponível.',
        )
    },
)
def consultar_previsoes(
    request: Request,
    sku: str | None = None,
    granularidade: Literal['diaria', 'semanal'] | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
    deslocamento: Annotated[int, Query(ge=0)] = 0,
) -> RespostaHistorico:
    """Consulta a tabela do serviço; filtros e paginação são opcionais."""
    if sku is not None:
        try:
            sku = normalizar_sku(sku)
        except ValueError as erro:
            raise SkuInexistente(str(erro), campo='sku') from erro
    itens, total = request.app.state.historico.consultar(
        sku, granularidade, limite, deslocamento
    )
    return RespostaHistorico(
        total=total,
        limite=limite,
        deslocamento=deslocamento,
        itens=[ItemPrevisaoHistorica(**item.__dict__) for item in itens],
    )


@router.get(
    '/previsoes/exportacao.xlsx',
    summary='Exporta previsões já servidas para XLSX',
    responses={
        200: {
            'content': {
                _MIME_XLSX: {'schema': {'type': 'string', 'format': 'binary'}}
            }
        },
        503: _erro(
            'Histórico indisponível.',
            'historico_indisponivel',
            'O histórico de previsões não está disponível.',
        ),
    },
)
def exportar_previsoes(
    request: Request,
    sku: str | None = None,
    granularidade: Literal['diaria', 'semanal'] | None = None,
) -> StreamingResponse:
    """Exporta todos os períodos filtrados; não inclui confiança removida."""
    if sku is not None:
        try:
            sku = normalizar_sku(sku)
        except ValueError as erro:
            raise SkuInexistente(str(erro), campo='sku') from erro
    itens, _ = request.app.state.historico.consultar(
        sku, granularidade, limite=None
    )
    corpo = consultas.gerar_xlsx(itens)
    nome = f'previsoes-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.xlsx'
    return StreamingResponse(
        BytesIO(corpo),
        media_type=_MIME_XLSX,
        headers={'Content-Disposition': f'attachment; filename="{nome}"'},
    )


@router.get(
    '/modelos',
    response_model=RespostaModelos,
    summary='Consulta versões de modelos no Registry',
    responses={
        503: _erro(
            'Registry indisponível.',
            'modelo_indisponivel',
            'O catálogo de modelos não está disponível.',
        )
    },
)
def consultar_modelos(request: Request) -> RespostaModelos:
    """Lista versões e aliases; não baixa modelos nem dispara treino."""
    return RespostaModelos(
        modelos=consultas.listar_modelos(request.app.state.cfg)
    )


@router.get(
    '/series/{sku}/{granularidade}',
    response_model=SerieHistorica,
    summary='Consulta histórico de vendas da rede',
    responses={
        404: _erro('SKU inexistente.', 'sku_inexistente', 'SKU desconhecido.'),
        503: _erro(
            'Série indisponível.',
            'historico_indisponivel',
            'A série de desenvolvimento não está disponível.',
        ),
    },
)
def consultar_serie(
    request: Request,
    sku: str,
    granularidade: Literal['diaria', 'semanal'],
) -> SerieHistorica:
    """Lê apenas o banco de desenvolvimento, que não contém o OOT."""
    try:
        sku = normalizar_sku(sku)
    except ValueError as erro:
        raise SkuInexistente(str(erro), campo='sku') from erro
    if sku not in SKUS:
        raise SkuInexistente(f'SKU desconhecido: {sku}.', campo='sku')
    pontos = consultas.carregar_serie(
        request.app.state.cfg, sku, granularidade
    )
    return SerieHistorica(sku=sku, granularidade=granularidade, pontos=pontos)
