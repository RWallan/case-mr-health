"""Schemas de histórico, versões, séries e exportação (#16, #22)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ItemPrevisaoHistorica(BaseModel):
    id_requisicao: str
    sku: str
    granularidade: Literal['diaria', 'semanal']
    data_geracao: datetime
    data_referencia: date
    data_alvo: date
    versao_modelo: str
    hash_artefato: str
    quantidade_prevista: float
    valor_unitario: float
    valor_previsto: float
    limite_inferior_80: float | None
    limite_superior_80: float | None
    limite_inferior_95: float | None
    limite_superior_95: float | None
    experimento_id: str
    run_id: str


class RespostaHistorico(BaseModel):
    total: int = Field(
        description='Total de períodos que atendem aos filtros.'
    )
    limite: int = Field(description='Máximo de itens nesta página.')
    deslocamento: int = Field(description='Número de itens ignorados.')
    itens: list[ItemPrevisaoHistorica] = Field(
        description='Previsões servidas por período-alvo.'
    )


class VersaoDisponivel(BaseModel):
    sku: str
    granularidade: Literal['diaria', 'semanal']
    versao: str
    aliases: list[str]
    champion: bool
    algoritmo: str | None
    hash_artefato: str | None
    run_id: str | None
    criada_em: datetime


class RespostaModelos(BaseModel):
    modelos: list[VersaoDisponivel]


class PontoHistorico(BaseModel):
    data: date
    quantidade: float
    imputado: bool = Field(
        description='True quando zero representa dia sem venda imputado.'
    )


class SerieHistorica(BaseModel):
    sku: str
    granularidade: Literal['diaria', 'semanal']
    pontos: list[PontoHistorico]
