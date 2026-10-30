"""Corpo único dos erros da API."""

from pydantic import BaseModel, Field


class DetalheErro(BaseModel):
    campo: str = Field(description='Campo com problema.')
    mensagem: str = Field(description='O que está errado no campo.')


class ErroResposta(BaseModel):
    codigo: str = Field(
        description='Identificador estável do erro, para uso por programas.'
    )
    mensagem: str = Field(description='Explicação e justificativa do erro.')
    detalhes: list[DetalheErro] = Field(
        default_factory=list, description='Campos com problema, se houver.'
    )
