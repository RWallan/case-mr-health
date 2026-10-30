from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TipoMudanca(StrEnum):
    """Tipos de `[tool.towncrier.type]`, com o título que vai no arquivo."""

    ADICIONADO = 'Adicionado'
    CORRECOES = 'Correções'
    ALTERADO = 'Alterado'
    REMOVIDO = 'Removido'
    ATUALIZACOES = 'Atualizações'
    INTERNO = 'Interno'


class Item(BaseModel):
    """Uma mudança, sem os links de issue no fim do texto."""

    texto: str = Field(description='Descrição da mudança.')
    issues: list[int] = Field(
        description='IDs das issues ligadas; vazia em mudanças sem issue.',
    )


class Secao(BaseModel):
    """Mudanças de uma versão agrupadas por tipo."""

    tipo: TipoMudanca = Field(description='Tipo da mudança.')
    itens: list[Item] = Field(description='Mudanças deste tipo.')


class Versao(BaseModel):
    """Uma versão publicada."""

    versao: str = Field(description='Número da versão (SemVer).')
    data: date = Field(description='Data da versão.')
    secoes: list[Secao] = Field(description='Seções na ordem do arquivo.')


class Changelog(BaseModel):
    """Changelog do projeto, com as versões na ordem do arquivo."""

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'versoes': [
                        {
                            'versao': '0.3.0',
                            'data': '2026-10-30',
                            'secoes': [
                                {
                                    'tipo': 'Adicionado',
                                    'itens': [
                                        {
                                            'texto': (
                                                'Intervalos de previsão de '
                                                '80% e 95%.'
                                            ),
                                            'issues': [8],
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    )

    versoes: list[Versao] = Field(
        description='Versões; vazia se o changelog faltar ou estiver vazio.',
    )
