"""Schemas da atualização de dados e do reajuste (#30, ADR 0011)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AVISO = (
    'Versões reajustadas não têm métrica fora da amostra: o backtest e o '
    'OOT descrevem a versão original (ADR 0011).'
)
EstadoAtualizacao = Literal[
    'em_andamento', 'concluida', 'concluida_com_erros', 'falhou'
]
EstadoSerie = Literal['reajustada', 'ignorada', 'falhou']


class SerieAtualizada(BaseModel):
    sku: str
    granularidade: Literal['diaria', 'semanal']
    estado: EstadoSerie = Field(
        description=(
            '`reajustada`, `ignorada` (série sem versão servida para '
            'reajustar) ou `falhou` (a versão servida não mudou).'
        )
    )
    versao_anterior: str | None = None
    versao_nova: str | None = None
    servida: bool = Field(
        default=False,
        description=(
            'Se a API passou a servir a versão nova. Falso quando a série '
            'tem versão fixada por configuração.'
        ),
    )
    erro: str | None = None


class RespostaAtualizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'id': '6d1f0f0a2b7a4c0e9d3a6b1f2c4e8a90',
                    'estado': 'em_andamento',
                    'hash_dados': 'c0ffee…',
                    'pedidos_novos': 12,
                    'itens_novos': 20,
                    'ultimo_dia': '2021-09-14',
                    'iniciada_em': '2026-10-30T09:40:00-03:00',
                    'concluida_em': None,
                    'series': [],
                    'aviso': AVISO,
                }
            ]
        }
    )

    id: str = Field(description='Use em `GET /dados/atualizacoes/{id}`.')
    estado: EstadoAtualizacao
    hash_dados: str = Field(
        description='Hash dos dados resultantes; vai nas tags das versões.'
    )
    pedidos_novos: int
    itens_novos: int
    ultimo_dia: date = Field(description='Último dia com pedido na base.')
    iniciada_em: datetime
    concluida_em: datetime | None
    series: list[SerieAtualizada] = Field(
        description='Uma entrada por série, preenchida conforme o reajuste.'
    )
    aviso: str = AVISO
