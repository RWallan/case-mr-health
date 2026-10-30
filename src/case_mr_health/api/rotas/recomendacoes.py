"""Rota da recomendação determinística (#19)."""

from fastapi import APIRouter, Request

from case_mr_health.api.schemas.erros import ErroResposta
from case_mr_health.api.schemas.recomendacao import RespostaRecomendacao
from case_mr_health.api.servicos import recomendacao

router = APIRouter(tags=['Recomendação'])


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
    '/recomendacoes/{sku}',
    response_model=RespostaRecomendacao,
    summary='Recomendação de estoque de um SKU',
    responses={
        404: _erro(
            'SKU inexistente.',
            'sku_inexistente',
            "SKU desconhecido: item Z; use um de ('item A', ...)",
        ),
        503: _erro(
            'Sem modelo semanal servível, ou histórico/série indisponível.',
            'modelo_indisponivel',
            'Sem modelo para item C/semanal: sem alias champion. A API não '
            'usa outro modelo nem treina um novo.',
        ),
    },
)
def consultar_recomendacao(sku: str, request: Request) -> RespostaRecomendacao:
    """Compara a demanda prevista (2 semanas) com a venda recente (4).

    Usa o modelo semanal (`champion` ou versão fixada) da **rede**. A
    variação é significativa quando passa do Q3 das variações históricas do
    mesmo sentido; com menos de 3 delas, ou sem venda recente, o resultado
    é `insuficiente`. A decisão é só da regra: nenhum LLM participa, e o
    texto fala em pressão sobre o estoque, nunca em ruptura. Toda resposta
    leva o aviso de baixa confiabilidade estatística, e a chamada é gravada
    no histórico de previsões.
    """
    estado = request.app.state
    return recomendacao.recomendar_sku(
        sku, estado.modelos, estado.historico, estado.cfg
    )
