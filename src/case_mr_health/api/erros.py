"""Erros de negócio e sua tradução para o corpo `ErroResposta`."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from case_mr_health.api.schemas.erros import DetalheErro, ErroResposta

_MENSAGENS_VALIDACAO = {
    'missing': 'campo obrigatório ausente',
    'extra_forbidden': 'campo não faz parte do contrato',
    'int_type': 'deve ser um número inteiro',
    'int_parsing': 'deve ser um número inteiro',
    'string_type': 'deve ser um texto',
    'string_too_short': 'não pode ser vazio',
    'greater_than_equal': 'deve ser maior ou igual a 1',
    'json_invalid': 'o corpo não é um JSON válido',
    'model_attributes_type': 'o corpo deve ser um objeto JSON',
}
_PREFIXO_PYDANTIC = 'Value error, '


class ErroApi(Exception):
    """Erro de negócio; subclasses fixam o status e o código."""

    status = 500
    codigo = 'erro_interno'

    def __init__(
        self,
        mensagem: str,
        campo: str | None = None,
        detalhes: list[DetalheErro] | None = None,
    ):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campo = campo
        self.detalhes = detalhes


class SkuInexistente(ErroApi):
    status = 404
    codigo = 'sku_inexistente'


class ModeloIndisponivel(ErroApi):
    status = 503
    codigo = 'modelo_indisponivel'


class HistoricoIndisponivel(ErroApi):
    status = 503
    codigo = 'historico_indisponivel'


class HorizonteAcimaDoLimite(ErroApi):
    status = 422
    codigo = 'horizonte_acima_do_limite'


class DataReferenciaInvalida(ErroApi):
    status = 422
    codigo = 'data_referencia_invalida'


class DadosInvalidos(ErroApi):
    status = 422
    codigo = 'dados_invalidos'


class AtualizacaoRecusada(ErroApi):
    status = 409
    codigo = 'atualizacao_recusada'


class AtualizacaoInexistente(ErroApi):
    status = 404
    codigo = 'atualizacao_inexistente'


def _erro_api(_: Request, erro: ErroApi) -> JSONResponse:
    detalhes = erro.detalhes or []
    if not detalhes and erro.campo is not None:
        detalhes = [DetalheErro(campo=erro.campo, mensagem=erro.mensagem)]
    corpo = ErroResposta(
        codigo=erro.codigo, mensagem=erro.mensagem, detalhes=detalhes
    )
    return JSONResponse(corpo.model_dump(), status_code=erro.status)


def _detalhe(erro: dict) -> DetalheErro:
    tipo = erro['type']
    if tipo == 'json_invalid':
        campo = 'corpo'
    else:
        campo = '.'.join(str(p) for p in erro['loc'] if p != 'body') or 'corpo'
    mensagem = _MENSAGENS_VALIDACAO.get(tipo, erro['msg'])
    return DetalheErro(
        campo=campo, mensagem=mensagem.removeprefix(_PREFIXO_PYDANTIC)
    )


def _erro_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    corpo = ErroResposta(
        codigo='requisicao_invalida',
        mensagem='A requisição não atende ao contrato de entrada.',
        detalhes=[_detalhe(e) for e in erro.errors()],
    )
    return JSONResponse(corpo.model_dump(), status_code=422)


def registrar_tratadores(app: FastAPI) -> None:
    app.add_exception_handler(ErroApi, _erro_api)
    app.add_exception_handler(RequestValidationError, _erro_validacao)
