"""Rotas da predição em lote, por XLSX e do template (#15)."""

from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response

from case_mr_health.api.schemas.erros import ErroResposta
from case_mr_health.api.schemas.lote import PedidoLote, RespostaLote
from case_mr_health.api.servicos import lote

router = APIRouter(tags=['Predição em lote'])


def _erro(descricao: str, codigo: str, mensagem: str, detalhes) -> dict:
    return {
        'model': ErroResposta,
        'description': descricao,
        'content': {
            'application/json': {
                'example': {
                    'codigo': codigo,
                    'mensagem': mensagem,
                    'detalhes': detalhes,
                }
            }
        },
    }


_ERRO_JSON = _erro(
    (
        'Alguma solicitação é inválida; o lote é tudo ou nada. Cada '
        'problema traz o campo (`itens.<posição>.<campo>`).'
    ),
    'lote_invalido',
    '1 solicitação(ões) inválida(s); nada foi previsto nem gravado.',
    [
        {
            'campo': 'itens.1.horizonte',
            'mensagem': 'Horizonte 15 acima do limite: ...',
        }
    ],
)
_ERRO_XLSX = _erro(
    (
        'Planilha inválida; nada é previsto. Cada problema traz a linha '
        'da planilha (cabeçalho = 1) e a coluna.'
    ),
    'lote_invalido',
    '1 problema(s) na planilha; nada foi previsto.',
    [
        {
            'campo': 'linha 3 / sku',
            'mensagem': 'SKU desconhecido: item Z; ...',
        }
    ],
)
_ERRO_503 = _erro(
    'Histórico indisponível.',
    'historico_indisponivel',
    'A previsão não foi servida porque não pôde ser registrada.',
    [],
)


@router.post(
    '/predicoes/lote',
    response_model=RespostaLote,
    summary='Prevê várias combinações de SKU e granularidade de uma vez',
    responses={422: _ERRO_JSON, 503: _ERRO_503},
)
def criar_lote(pedido: PedidoLote, request: Request) -> RespostaLote:
    """Cada item segue as regras da predição individual (`POST /predicoes`).

    Todos os itens são validados antes de qualquer previsão: se algum for
    inválido (SKU, granularidade, data, horizonte ou modelo indisponível),
    a resposta é 422 com todos os problemas e nada é gravado. No máximo 200
    itens (`LIMITE_LOTE`). Cada período servido vai ao histórico.
    """
    estado = request.app.state
    return lote.prever_lote(
        lote.solicitacoes_do_json(pedido.itens),
        estado.modelos,
        estado.historico,
        estado.cfg,
    )


@router.post(
    '/predicoes/lote/xlsx',
    response_model=RespostaLote,
    summary='Prevê as solicitações de uma planilha XLSX',
    responses={422: _ERRO_XLSX, 503: _ERRO_503},
)
def criar_lote_xlsx(
    request: Request,
    arquivo: Annotated[
        UploadFile,
        File(description='Planilha no formato do template.'),
    ],
) -> RespostaLote:
    """Mesmas regras do lote em JSON, com o erro apontando a linha.

    Baixe o template em `GET /predicoes/lote/template.xlsx`. Colunas:
    `sku`, `granularidade`, `data_referencia` e, opcional, `horizonte`.
    Qualquer erro cancela o arquivo inteiro.
    """
    estado = request.app.state
    solicitacoes, problemas = lote.solicitacoes_do_xlsx(arquivo.file.read())
    return lote.prever_lote(
        solicitacoes,
        estado.modelos,
        estado.historico,
        estado.cfg,
        problemas,
    )


@router.get(
    '/predicoes/lote/template.xlsx',
    summary='Baixa o template XLSX da predição em lote',
    response_class=Response,
    responses={
        200: {
            'description': (
                'Planilha com as colunas, exemplos válidos e uma aba de '
                'instruções de preenchimento.'
            ),
            'content': {lote.MIME_XLSX: {}},
        }
    },
)
def baixar_template(request: Request) -> Response:
    """Template com as colunas obrigatórias, exemplos e instruções."""
    estado = request.app.state
    return Response(
        lote.template_xlsx(estado.modelos, estado.cfg),
        media_type=lote.MIME_XLSX,
        headers={
            'Content-Disposition': (
                'attachment; filename="template-predicao-em-lote.xlsx"'
            )
        },
    )
