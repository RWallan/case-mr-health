"""Rota da recomendação determinística (#19)."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from case_mr_health.api.schemas.erros import ErroResposta
from case_mr_health.api.schemas.recomendacao import RespostaRecomendacao
from case_mr_health.api.servicos import recomendacao
from case_mr_health.explicacao import gerador_do_usuario

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
def consultar_recomendacao(
    sku: str,
    request: Request,
    x_llm_modelo: Annotated[
        str | None,
        Header(
            description=(
                'Modelo do LLM na notação do litellm, por exemplo '
                '`openai/gpt-4o`, `anthropic/claude-sonnet-5-5` ou '
                '`gemini/gemini-2.0-flash`. Vale só com `X-LLM-Chave`.'
            ),
        ),
    ] = None,
    x_llm_chave: Annotated[
        str | None,
        Header(
            description=(
                'Chave de API do usuário para o provedor do modelo. Usada '
                'só nesta chamada; não é armazenada nem registrada em log.'
            ),
        ),
    ] = None,
) -> RespostaRecomendacao:
    """Compara a demanda prevista (2 semanas) com a venda recente (4).

    Usa o modelo semanal (`champion` ou versão fixada) da **rede**. A
    variação é significativa quando passa do Q3 das variações históricas do
    mesmo sentido; com menos de 3 delas, ou sem venda recente, o resultado
    é `insuficiente`. A decisão é só da regra: nenhum LLM participa, e o
    texto fala em pressão sobre o estoque, nunca em ruptura. Toda resposta
    leva a `explicacao` (campo `origem`: `llm` ou `template`) e o aviso de
    baixa confiabilidade estatística, e a chamada é gravada no histórico de
    previsões.

    A explicação é gerada por um LLM de qualquer provedor (litellm), com o
    modelo e a chave que o usuário informa nos cabeçalhos `X-LLM-Modelo` e
    `X-LLM-Chave`; sem eles, vale a configuração do servidor. Sem
    ferramentas nem acesso externo, a partir dos números
    da regra. A saída é validada por schema e só pode citar números da
    entrada; sem chave, com falha ou com saída inválida, vem o template
    determinístico. A explicação nunca altera o resultado.
    """
    estado = request.app.state
    gerador = (
        gerador_do_usuario(estado.cfg, x_llm_modelo, x_llm_chave)
        or estado.gerador_llm
    )
    return recomendacao.recomendar_sku(
        sku,
        estado.modelos,
        estado.historico,
        estado.cfg,
        gerador,
    )
