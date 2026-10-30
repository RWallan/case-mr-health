"""Contrato do e-mail de alerta mockado (#21)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from case_mr_health.api.schemas.predicao import PeriodoPrevisto
from case_mr_health.recomendacao import Motivo, Resultado


class PedidoAlertaEmail(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'examples': [{'email': 'gestor@exemplo.com.br', 'sku': 'item A'}]
        },
    )

    email: EmailStr = Field(
        description='Endereço do gestor; é validado, mas nada é enviado.'
    )
    sku: str = Field(
        min_length=1, description='SKU do alerta: `item A` ou só `A`.'
    )


class RecomendacaoAlerta(BaseModel):
    """Recomendação do #19 embutida no alerta."""

    resultado: Resultado = Field(
        description=(
            '`aumento_significativo`, `reducao_significativa`, `estavel` '
            'ou `insuficiente`.'
        )
    )
    motivo: Motivo | None = Field(
        description='Só em `insuficiente`; `null` nos demais.'
    )
    variacao: float | None = Field(
        description='Fração (0,25 é 25%); `null` sem venda recente.'
    )
    limite_aplicado: float | None = Field(
        description='Q3 histórico do mesmo sentido; `null` se não calculado.'
    )
    media_vendida_4s: float = Field(
        description='Venda média semanal das 4 últimas semanas completas.'
    )
    media_prevista_2s: float = Field(
        description='Demanda média semanal prevista para as 2 próximas.'
    )
    n_variacoes_positivas: int = Field(
        description='Variações históricas positivas.'
    )
    n_variacoes_negativas: int = Field(
        description='Variações históricas negativas.'
    )
    texto: str = Field(
        description='Explicação em português; nunca afirma ruptura.'
    )
    aviso: str = Field(
        description='Aviso de baixa confiabilidade estatística.'
    )


class RespostaAlertaEmail(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            'examples': [
                {
                    'id_requisicao': '9f1c2a70-3f4e-4f0e-9d51-4a1c6d7e8b90',
                    'envio_simulado': True,
                    'aviso_envio': (
                        'Envio simulado: nada foi enviado para '
                        'gestor@exemplo.com.br.'
                    ),
                    'destinatario': 'gestor@exemplo.com.br',
                    'assunto': 'Alerta de demanda: item A (semanal)',
                    'sku': 'item A',
                    'granularidade': 'semanal',
                    'nivel': 'rede',
                    'periodos': [
                        {
                            'data_alvo': '2021-08-16',
                            'quantidade_prevista': 24.0,
                            'valor_previsto': 240.0,
                            'limite_inferior_80': 10.0,
                            'limite_superior_80': 38.0,
                            'limite_inferior_95': 5.0,
                            'limite_superior_95': 43.0,
                        }
                    ],
                    'valor_total_previsto': 240.0,
                    'recomendacao': {
                        'resultado': 'aumento_significativo',
                        'motivo': None,
                        'variacao': 0.4706,
                        'limite_aplicado': 0.3069,
                        'media_vendida_4s': 17.0,
                        'media_prevista_2s': 25.0,
                        'n_variacoes_positivas': 6,
                        'n_variacoes_negativas': 0,
                        'texto': 'Aumento significativo: ...',
                        'aviso': (
                            'baixa confiabilidade estatística: poucas '
                            'janelas históricas'
                        ),
                    },
                    'versao_modelo': '3',
                    'hash_artefato': 'a3f5…',
                    'origem_modelo': 'treino',
                }
            ]
        },
    )

    id_requisicao: str = Field(
        description='Identificador da chamada no histórico de previsões.'
    )
    envio_simulado: Literal[True] = Field(
        default=True,
        description='Sempre `true`: nenhum e-mail real é enviado.',
    )
    aviso_envio: str = Field(
        description='Texto explícito de que nada foi enviado.'
    )
    destinatario: str = Field(description='E-mail informado, validado.')
    assunto: str = Field(description='Assunto que o e-mail teria.')
    sku: str = Field(description='SKU normalizado.')
    granularidade: Literal['semanal'] = Field(
        default='semanal', description='O alerta usa o modelo semanal.'
    )
    nivel: Literal['rede'] = Field(
        default='rede', description='A série é da rede.'
    )
    periodos: list[PeriodoPrevisto] = Field(
        description=(
            'As 2 semanas previstas: demanda, valor e intervalos de 80% e '
            '95%. Limite `null` significa intervalo indisponível.'
        )
    )
    valor_total_previsto: float = Field(
        description='Soma de `valor_previsto` das semanas.'
    )
    recomendacao: RecomendacaoAlerta = Field(
        description='Recomendação determinística (#19).'
    )
    versao_modelo: str = Field(description='Versão semanal servida.')
    hash_artefato: str = Field(description='Hash do artefato da versão.')
    origem_modelo: Literal['treino', 'atualizacao'] = Field(
        default='treino',
        description=(
            '`atualizacao`: versão reajustada, sem métrica fora da amostra.'
        ),
    )
