"""Rota da predição individual (#14)."""

from fastapi import APIRouter, Request

from case_mr_health.api.schemas.erros import ErroResposta
from case_mr_health.api.schemas.predicao import (
    PedidoPredicao,
    RespostaPredicao,
)
from case_mr_health.api.servicos import predicao

router = APIRouter(tags=['Predição'])


def _resposta_erro(descricao: str, **exemplo) -> dict:
    return {
        'model': ErroResposta,
        'description': descricao,
        'content': {'application/json': {'example': exemplo}},
    }


_ERROS = {
    404: _resposta_erro(
        'SKU inexistente.',
        codigo='sku_inexistente',
        mensagem="SKU desconhecido: item Z; use um de ('item A', ...)",
        detalhes=[
            {'campo': 'sku', 'mensagem': 'SKU desconhecido: item Z; ...'}
        ],
    ),
    422: _resposta_erro(
        (
            'Entrada inválida: campo obrigatório ausente, data inválida, '
            'granularidade mensal ou não suportada, ou horizonte acima do '
            'limite validado '
            '(`requisicao_invalida`, `data_referencia_invalida` ou '
            '`horizonte_acima_do_limite`).'
        ),
        codigo='horizonte_acima_do_limite',
        mensagem=(
            'Horizonte 15 acima do limite: o máximo validado empiricamente '
            'é de 14 dias depois do fim do treino (tamanho do período OOT); '
            'além disso, o horizonte não tem validação.'
        ),
        detalhes=[{'campo': 'horizonte', 'mensagem': '...'}],
    ),
    503: _resposta_erro(
        (
            'Sem modelo servível para a série (sem `champion` nem versão '
            'fixada, ou hash divergente), ou histórico indisponível '
            '(`modelo_indisponivel` ou `historico_indisponivel`). A API '
            'nunca usa outro modelo nem treina um novo.'
        ),
        codigo='modelo_indisponivel',
        mensagem=(
            'Sem modelo para item C/semanal: demanda-item-c-semanal sem '
            'alias champion. A API não usa outro modelo nem treina um novo.'
        ),
        detalhes=[],
    ),
}


@router.post(
    '/predicoes',
    summary='Prevê a demanda da rede para um SKU',
    responses=_ERROS,
)
def criar_predicao(
    pedido: PedidoPredicao, request: Request
) -> RespostaPredicao:
    """Prevê os períodos seguintes à data de referência, sem treinar nada.

    `data_referencia` é opcional: ausente, vale o fim do treino do modelo
    servido, e a resposta devolve a data usada, que é o início da previsão
    (ADR 0013).

    A previsão é da **rede**, com a versão `champion` (ou a fixada por
    configuração) da série pedida. O modelo foi ajustado até o fim do
    treino e não vê dados depois dele: a data de referência escolhe quais
    passos à frente são servidos, e o último passo não pode passar do
    máximo validado. Cada período-alvo é gravado no histórico de previsões.
    """
    estado = request.app.state
    return predicao.prever(
        pedido, estado.modelos, estado.historico, estado.cfg
    )
