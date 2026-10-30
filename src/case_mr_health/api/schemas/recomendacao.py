"""Schemas da recomendação determinística (#19)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from case_mr_health.recomendacao import Motivo, Resultado

AVISO = 'baixa confiabilidade estatística: poucas janelas históricas'


class RespostaRecomendacao(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            'examples': [
                {
                    'id_requisicao': '9f1c2a70-3f4e-4f0e-9d51-4a1c6d7e8b90',
                    'sku': 'item A',
                    'granularidade': 'semanal',
                    'nivel': 'rede',
                    'resultado': 'aumento_significativo',
                    'motivo': None,
                    'variacao': 0.4706,
                    'limite_aplicado': 0.3069,
                    'media_vendida_4s': 17.0,
                    'media_prevista_2s': 25.0,
                    'n_variacoes_positivas': 6,
                    'n_variacoes_negativas': 0,
                    'texto': (
                        'Aumento significativo: a demanda média prevista '
                        'para as próximas 2 semanas (25,0) supera em '
                        '47,1% a venda média das últimas 4 semanas '
                        '(17,0), acima do limite histórico de 30,7%. '
                        'Indica pressão de alta sobre o estoque.'
                    ),
                    'aviso': AVISO,
                    'versao_modelo': '3',
                    'hash_artefato': 'a3f5…',
                }
            ]
        },
    )

    id_requisicao: str = Field(
        description='Identificador da chamada no histórico de previsões.'
    )
    sku: str = Field(description='SKU normalizado.')
    granularidade: Literal['semanal'] = Field(
        default='semanal',
        description='A recomendação usa só o modelo semanal.',
    )
    nivel: Literal['rede'] = Field(
        default='rede', description='A série é da rede.'
    )
    resultado: Resultado = Field(
        description=(
            '`aumento_significativo`, `reducao_significativa`, `estavel` '
            'ou `insuficiente`.'
        )
    )
    motivo: Motivo | None = Field(
        description=(
            'Só em `insuficiente`: `sem_venda_recente` (média das 4 '
            'últimas semanas igual a 0) ou `variacoes_insuficientes` '
            '(menos de 3 variações históricas do lado da variação atual).'
        )
    )
    variacao: float | None = Field(
        description=(
            '(média prevista nas 2 próximas semanas − média vendida nas 4 '
            'últimas) ÷ média vendida nas 4 últimas. Fração: 0,25 é 25%.'
        )
    )
    limite_aplicado: float | None = Field(
        description=(
            'Q3 (interpolação linear) das variações históricas do lado da '
            'variação atual, em módulo. `null` quando não foi calculado.'
        )
    )
    media_vendida_4s: float = Field(
        description='Venda média semanal das 4 últimas semanas completas.'
    )
    media_prevista_2s: float = Field(
        description='Demanda média semanal prevista para as 2 próximas.'
    )
    n_variacoes_positivas: int = Field(
        description='Variações históricas positivas (janelas válidas).'
    )
    n_variacoes_negativas: int = Field(
        description='Variações históricas negativas (janelas válidas).'
    )
    texto: str = Field(
        description=(
            'Explicação em português. Fala em "pressão sobre o estoque" e '
            'nunca afirma ruptura.'
        )
    )
    aviso: str = Field(
        description='Presente em toda resposta, inclusive `estavel`.'
    )
    versao_modelo: str = Field(description='Versão semanal servida.')
    hash_artefato: str = Field(description='Hash do artefato da versão.')
