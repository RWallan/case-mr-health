"""Contrato da predição em lote e por XLSX (#15)."""

from pydantic import BaseModel, ConfigDict, Field

from case_mr_health.api.schemas.predicao import (
    PedidoPredicao,
    RespostaPredicao,
)

LIMITE_LOTE = 200


class PedidoLote(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'examples': [
                {
                    'itens': [
                        {
                            'sku': 'item A',
                            'granularidade': 'diaria',
                            'horizonte': 3,
                        },
                        {
                            'sku': 'B',
                            'granularidade': 'semanal',
                        },
                    ]
                }
            ]
        },
    )

    itens: list[PedidoPredicao] = Field(
        min_length=1,
        max_length=LIMITE_LOTE,
        description=(
            'Solicitações de previsão, cada uma com as regras da predição '
            f'individual. No máximo {LIMITE_LOTE} por lote.'
        ),
    )


class ItemLote(BaseModel):
    indice: int = Field(description='Posição do item no lote, de 0 em diante.')
    linha: int | None = Field(
        default=None,
        description='Linha da planilha (cabeçalho = 1); só no envio XLSX.',
    )
    previsao: RespostaPredicao


class RespostaLote(BaseModel):
    total: int = Field(description='Quantidade de solicitações atendidas.')
    resultados: list[ItemLote] = Field(
        description=(
            'Uma resposta por solicitação, na ordem enviada. O lote é '
            'tudo ou nada: se qualquer item for inválido, nenhum é previsto '
            'nem gravado no histórico.'
        )
    )
