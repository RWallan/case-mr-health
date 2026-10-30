"""Rotas da atualização de dados com reajuste (#30, ADR 0011)."""

from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from case_mr_health.api.schemas.atualizacao import RespostaAtualizacao
from case_mr_health.api.schemas.erros import ErroResposta

router = APIRouter(tags=['Atualização de dados'])


def _erro(descricao: str, codigo: str, mensagem: str, detalhes=()) -> dict:
    return {
        'model': ErroResposta,
        'description': descricao,
        'content': {
            'application/json': {
                'example': {
                    'codigo': codigo,
                    'mensagem': mensagem,
                    'detalhes': list(detalhes),
                }
            }
        },
    }


@router.post(
    '/dados/pedidos',
    status_code=202,
    response_model=RespostaAtualizacao,
    summary='Envia pedidos novos e reajusta os modelos',
    responses={
        409: _erro(
            'Já há uma atualização em andamento, ou este par de planilhas '
            'já foi aplicado.',
            'atualizacao_recusada',
            'Já existe uma atualização em andamento; aguarde o fim.',
        ),
        422: _erro(
            'Planilhas inválidas; nada é aplicado. Cada problema traz a '
            'planilha e a linha.',
            'dados_invalidos',
            'As planilhas não passaram na validação; nada foi aplicado.',
            [
                {
                    'campo': 'ITEM_PEDIDO linha 4',
                    'mensagem': "SKU 'item Z' sem cadastro.",
                }
            ],
        ),
    },
)
def enviar_pedidos(
    request: Request,
    pedidos: Annotated[
        UploadFile, File(description='XLSX de pedidos (ID_PEDIDO, DATA).')
    ],
    itens: Annotated[
        UploadFile,
        File(description='XLSX de itens de pedido (ID_PEDIDO, ID_ITEM, QTD).'),
    ],
) -> RespostaAtualizacao:
    """Acrescenta os pedidos novos à base e reajusta os modelos das séries.

    Os arquivos têm o formato das planilhas brutas e são validados na
    própria requisição, com as mesmas regras da preparação de dados. Se
    forem válidos, a base e as séries são atualizadas e a resposta é 202:
    o reajuste (mesmo algoritmo e hiperparâmetros de cada versão servida,
    sem nova seleção) roda em segundo plano, uma atualização por vez, e
    cada série passa a servir a versão nova (`champion`) quando termina.
    Acompanhe em `GET /dados/atualizacoes/{id}`. Versões reajustadas não
    têm métrica fora da amostra.
    """
    return request.app.state.atualizacoes.iniciar(
        pedidos.file.read(), itens.file.read()
    )


@router.get(
    '/dados/atualizacoes/{id_atualizacao}',
    response_model=RespostaAtualizacao,
    summary='Acompanha uma atualização de dados',
    responses={
        404: _erro(
            'Atualização desconhecida (o estado só vive enquanto a API '
            'está de pé).',
            'atualizacao_inexistente',
            'Atualização abc desconhecida.',
        )
    },
)
def consultar_atualizacao(
    id_atualizacao: str, request: Request
) -> RespostaAtualizacao:
    """Estado da atualização e o resultado de cada série."""
    return request.app.state.atualizacoes.obter(id_atualizacao)
