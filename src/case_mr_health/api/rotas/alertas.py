"""Rota do e-mail de alerta mockado (#21)."""

from fastapi import APIRouter, Request

from case_mr_health.api.schemas.alertas import (
    PedidoAlertaEmail,
    RespostaAlertaEmail,
)
from case_mr_health.api.schemas.erros import ErroResposta
from case_mr_health.api.servicos import alertas

router = APIRouter(tags=['Alertas'])


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


@router.post(
    '/alertas/email',
    response_model=RespostaAlertaEmail,
    summary='E-mail de alerta simulado de um SKU',
    responses={
        404: _erro(
            'SKU inexistente.',
            'sku_inexistente',
            "SKU desconhecido: item Z; use um de ('item A', ...)",
        ),
        422: _erro(
            'E-mail inválido ou corpo fora do contrato.',
            'requisicao_invalida',
            'Requisição inválida.',
        ),
        503: _erro(
            'Sem modelo semanal servível, ou histórico/série indisponível.',
            'modelo_indisponivel',
            'Sem modelo para item C/semanal: sem alias champion.',
        ),
    },
)
def enviar_alerta_email(
    pedido: PedidoAlertaEmail, request: Request
) -> RespostaAlertaEmail:
    """Devolve o conteúdo do alerta de um SKU para o e-mail informado.

    **Nada é enviado.** O endereço é validado e a resposta traz
    `envio_simulado: true` e um aviso dizendo isso. O conteúdo reúne as 2
    semanas previstas (demanda, valor e intervalos de 80% e 95%) e a
    recomendação determinística do #19, com o aviso de baixa
    confiabilidade estatística. O contrato atual não tem campo de
    confiança por previsão, então ele não aparece. A chamada é gravada no
    histórico de previsões, como a recomendação.
    """
    estado = request.app.state
    return alertas.montar_alerta(
        pedido, estado.modelos, estado.historico, estado.cfg
    )
