"""Auditoria de segurança da chave do LLM (#44).

Injeta uma chave sentinela nos cabeçalhos e confere que ela não aparece nos
logs (loguru), no corpo nem nos cabeçalhos das respostas, inclusive quando o
LLM falha ou devolve a própria chave. Sem chamada real a provedor.
"""

import json

import pytest
from loguru import logger

from tests.test_api_recomendacao import AUMENTO, HTTP_OK, servir  # noqa: F401

SENTINELA = 'sk-SENTINELA-44-9f8e7d6c5b4a'
CABECALHOS = {'X-LLM-Modelo': 'openai/gpt-4o', 'X-LLM-Chave': SENTINELA}


class ErroValor(ValueError):
    """Exceção de provedor que herda de ValueError e cita a chave."""


def _resposta(litellm, texto):
    return litellm.ModelResponse(
        choices=[{'message': {'role': 'assistant', 'content': texto}}]
    )


def _generica(**kwargs):
    raise RuntimeError(f'timeout com api_key={kwargs["api_key"]}')


def _valor(**kwargs):
    raise ErroValor(f'chave inválida {kwargs["api_key"]}')


def _cenarios():
    import litellm  # noqa: PLC0415

    def autenticacao(**kwargs):
        raise litellm.AuthenticationError(
            f'Incorrect API key provided: {kwargs["api_key"]}',
            'openai',
            'gpt-4o',
        )

    return {
        'sucesso': lambda **_: _resposta(
            litellm, json.dumps({'texto': 'A média prevista é 25,0.'})
        ),
        'autenticacao': autenticacao,
        'excecao_generica': _generica,
        'excecao_value_error': _valor,
        'saida_ecoa_a_chave': lambda **_: _resposta(
            litellm, json.dumps({'texto': f'Use a chave {SENTINELA}'})
        ),
        'saida_invalida_com_a_chave': lambda **_: _resposta(
            litellm, f'não é json {SENTINELA}'
        ),
    }


@pytest.fixture
def logs():
    mensagens = []
    ident = logger.add(
        lambda m: mensagens.append(str(m)), level='DEBUG', backtrace=True
    )
    yield mensagens
    logger.remove(ident)


def _vazou(resposta, logs) -> list[str]:
    superficies = {
        'corpo': resposta.text,
        'cabecalhos': json.dumps(dict(resposta.headers)),
        'url': str(resposta.url),
        'logs': '\n'.join(logs),
    }
    return [k for k, v in superficies.items() if SENTINELA in v]


@pytest.mark.parametrize(
    'cenario',
    [
        'sucesso',
        'autenticacao',
        'excecao_generica',
        'excecao_value_error',
        'saida_ecoa_a_chave',
        'saida_invalida_com_a_chave',
    ],
)
def test_chave_sentinela_nao_vaza(servir, monkeypatch, logs, cenario):  # noqa: F811
    import litellm  # noqa: PLC0415

    monkeypatch.setattr(litellm, 'completion', _cenarios()[cenario])

    resposta = servir(AUMENTO, [24, 26]).get(
        '/recomendacoes/item A', headers=CABECALHOS
    )

    assert resposta.status_code == HTTP_OK
    assert _vazou(resposta, logs) == []
    origem = resposta.json()['explicacao']['origem']
    assert origem == ('llm' if cenario == 'sucesso' else 'template')


def test_chave_sentinela_nao_vaza_em_erro_da_api(servir, logs):  # noqa: F811
    resposta = servir(AUMENTO, [24, 26]).get(
        '/recomendacoes/item Z', headers=CABECALHOS
    )

    assert resposta.status_code != HTTP_OK
    assert _vazou(resposta, logs) == []


def test_cors_nao_expoe_a_chave(servir):  # noqa: F811
    resposta = servir(AUMENTO, [24, 26]).options(
        '/recomendacoes/item A',
        headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'x-llm-chave,x-llm-modelo',
        },
    )

    assert resposta.headers['access-control-allow-origin'] == (
        'http://localhost:5173'
    )
    assert 'access-control-allow-credentials' not in resposta.headers
    assert SENTINELA not in resposta.text
