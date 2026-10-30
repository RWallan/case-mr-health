"""Contrato da predição individual (#14)."""

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from case_mr_health.particoes import GRANULARIDADES

_DATA_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')
_MOTIVO_MENSAL = (
    'a mensal não é servida: 3 meses de histórico não permitem estimar nem '
    'validar um modelo (ADR 0001)'
)


class PedidoPredicao(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'examples': [
                {
                    'sku': 'item A',
                    'granularidade': 'diaria',
                    'horizonte': 3,
                }
            ]
        },
    )

    sku: str = Field(
        min_length=1, description='SKU da previsão: `item A` ou só `A`.'
    )
    granularidade: Literal['diaria', 'semanal'] = Field(
        description=(
            'Tamanho do período. A semanal só usa modelo semanal, e a diária, '
            'só modelo diário.'
        )
    )
    data_referencia: date | None = Field(
        default=None,
        description=(
            'Opcional. Último período conhecido pelo solicitante, '
            '`AAAA-MM-DD`; os períodos-alvo são os seguintes. Ausente, vale '
            'o fim do treino do modelo servido (ADR 0013). Na semanal, é '
            'normalizada para a segunda-feira da semana. Não pode ser '
            'anterior ao último período do treino do modelo.'
        ),
    )
    horizonte: int = Field(
        default=1,
        ge=1,
        strict=True,
        description=(
            'Períodos-alvo a prever. Somados aos períodos entre o fim do '
            'treino e a data de referência, não podem passar de 14 dias ou '
            '2 semanas, o máximo validado empiricamente.'
        ),
    )

    @field_validator('granularidade', mode='before')
    @classmethod
    def _granularidade_suportada(cls, valor):
        if valor not in GRANULARIDADES:
            raise ValueError(
                f'granularidade {valor!r} não suportada: use diaria ou '
                f'semanal; {_MOTIVO_MENSAL}'
            )
        return valor

    @field_validator('data_referencia', mode='before')
    @classmethod
    def _data_iso(cls, valor):
        """Só `AAAA-MM-DD`: número ou timestamp não viram data em silêncio."""
        if type(valor) is date:
            return valor
        try:
            if _DATA_ISO.fullmatch(valor):
                return date.fromisoformat(valor)
        except TypeError, ValueError:
            pass
        raise ValueError(f'data inválida: {valor!r}; use AAAA-MM-DD')


class PeriodoPrevisto(BaseModel):
    """Um período-alvo; intervalos não são agregados entre períodos."""

    data_alvo: date = Field(
        description='Dia previsto ou segunda-feira da semana prevista.'
    )
    quantidade_prevista: float = Field(
        description='Demanda prevista para a rede no período.'
    )
    valor_previsto: float = Field(
        description='Quantidade prevista vezes o valor unitário.'
    )
    limite_inferior_80: float | None = Field(
        description='Limite inferior de 80%, em quantidade.'
    )
    limite_superior_80: float | None = Field(
        description='Limite superior de 80%, em quantidade.'
    )
    limite_inferior_95: float | None = Field(
        description='Limite inferior de 95%, em quantidade.'
    )
    limite_superior_95: float | None = Field(
        description='Limite superior de 95%, em quantidade.'
    )


class RespostaPredicao(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            'examples': [
                {
                    'id_requisicao': '9f1c2a70-3f4e-4f0e-9d51-4a1c6d7e8b90',
                    'sku': 'item A',
                    'granularidade': 'diaria',
                    'nivel': 'rede',
                    'data_referencia': '2021-08-19',
                    'data_geracao': '2026-10-30T07:10:00-03:00',
                    'valor_unitario': 10.0,
                    'versao_modelo': '3',
                    'hash_artefato': 'a3f5…',
                    'origem_modelo': 'treino',
                    'experimento_id': '1',
                    'run_id': '0a2bbfbec17244318eae019bd4c0b91e',
                    'periodos': [
                        {
                            'data_alvo': '2021-08-20',
                            'quantidade_prevista': 12.5,
                            'valor_previsto': 125.0,
                            'limite_inferior_80': 0.0,
                            'limite_superior_80': 21.0,
                            'limite_inferior_95': 0.0,
                            'limite_superior_95': 27.0,
                        }
                    ],
                }
            ]
        },
    )

    id_requisicao: str = Field(
        description='Identificador da requisição no histórico de previsões.'
    )
    sku: str = Field(description='SKU normalizado.')
    granularidade: str = Field(description='`diaria` ou `semanal`.')
    nivel: Literal['rede'] = Field(
        default='rede',
        description=(
            'Nível da previsão. É sempre a rede: não há previsão por unidade.'
        ),
    )
    data_referencia: date = Field(
        description=(
            'Data de referência usada (a informada ou, se ausente, o fim do '
            'treino do modelo), normalizada na semanal. É o início da '
            'previsão: os períodos-alvo vêm depois dela.'
        )
    )
    data_geracao: datetime = Field(description='Momento em que foi gerada.')
    valor_unitario: float = Field(
        description='Valor unitário configurado do SKU.'
    )
    versao_modelo: str = Field(description='Versão registrada no MLflow.')
    hash_artefato: str = Field(
        description='Hash do artefato, conferido no carregamento.'
    )
    origem_modelo: Literal['treino', 'atualizacao'] = Field(
        default='treino',
        description=(
            '`atualizacao` indica versão reajustada com pedidos novos (ADR '
            '0011): não tem métrica fora da amostra.'
        ),
    )
    experimento_id: str = Field(description='Experimento MLflow de origem.')
    run_id: str = Field(description='Execução MLflow de origem.')
    periodos: list[PeriodoPrevisto] = Field(
        description=(
            'Um item por período-alvo. Limites de períodos diferentes não '
            'se somam: a soma dos limites não é o limite da soma. Limite '
            '`null` significa intervalo indisponível para a versão.'
        )
    )
