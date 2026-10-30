"""E-mail de alerta mockado (#21): rota (Seam 3).

Reaproveita as fixtures do #19. Nada é enviado: o teste proíbe `smtplib`.
"""

import smtplib

import pytest

from tests.test_api_recomendacao import (  # noqa: F401
    AUMENTO,
    AVISO,
    HTTP_INDISPONIVEL,
    HTTP_NAO_ENCONTRADO,
    HTTP_OK,
    servir,
)

HTTP_INVALIDO = 422
EMAIL = 'gestor@exemplo.com.br'
CHAVES = {
    'id_requisicao',
    'envio_simulado',
    'aviso_envio',
    'destinatario',
    'assunto',
    'sku',
    'granularidade',
    'nivel',
    'periodos',
    'valor_total_previsto',
    'recomendacao',
    'versao_modelo',
    'hash_artefato',
    'origem_modelo',
}


@pytest.fixture(autouse=True)
def sem_envio_real(monkeypatch):
    def _proibido(*_, **__):
        raise AssertionError('envio real de e-mail')

    monkeypatch.setattr(smtplib.SMTP, '__init__', _proibido)
    monkeypatch.setattr(smtplib.SMTP_SSL, '__init__', _proibido)


def _pedir(cliente, **extra):
    corpo = {'email': EMAIL, 'sku': 'item A', **extra}
    return cliente.post('/alertas/email', json=corpo)


def test_email_valido_devolve_conteudo_completo(servir):  # noqa: F811
    cliente = servir(AUMENTO, [24, 26])

    resposta = _pedir(cliente)

    assert resposta.status_code == HTTP_OK
    corpo = resposta.json()
    assert set(corpo) == CHAVES
    assert corpo['destinatario'] == EMAIL
    assert corpo['sku'] == 'item A'
    assert corpo['granularidade'] == 'semanal'
    assert corpo['nivel'] == 'rede'
    quantidades = [p['quantidade_prevista'] for p in corpo['periodos']]
    assert quantidades == [24, 26]
    periodo = corpo['periodos'][0]
    assert {'data_alvo', 'valor_previsto', 'limite_inferior_80'} <= set(
        periodo
    )
    assert corpo['valor_total_previsto'] == pytest.approx(
        sum(p['valor_previsto'] for p in corpo['periodos'])
    )
    assert corpo['recomendacao']['resultado'] == 'aumento_significativo'
    assert corpo['recomendacao']['aviso'] == AVISO
    assert 'item A' in corpo['assunto']


def test_resposta_avisa_que_nada_foi_enviado(servir):  # noqa: F811
    corpo = _pedir(servir(AUMENTO, [24, 26])).json()

    assert corpo['envio_simulado'] is True
    assert 'nada foi enviado' in corpo['aviso_envio'].lower()
    assert EMAIL in corpo['aviso_envio']


@pytest.mark.parametrize(
    'email', ['sem-arroba', 'a@', '@dominio.com', '', 'a b@exemplo.com']
)
def test_email_invalido_e_rejeitado(servir, email):  # noqa: F811
    cliente = servir(AUMENTO, [24, 26])

    resposta = _pedir(cliente, email=email)

    assert resposta.status_code == HTTP_INVALIDO
    _, total = cliente.app.state.historico.consultar('item A', None)
    assert total == 0


def test_campo_fora_do_contrato_e_rejeitado(servir):  # noqa: F811
    resposta = _pedir(servir(AUMENTO, [24, 26]), extra=1)

    assert resposta.status_code == HTTP_INVALIDO


def test_sku_inexistente_responde_404(servir):  # noqa: F811
    resposta = _pedir(servir(AUMENTO, [24, 26]), sku='item Z')

    assert resposta.status_code == HTTP_NAO_ENCONTRADO
    assert resposta.json()['codigo'] == 'sku_inexistente'


def test_sku_sem_modelo_responde_503(servir):  # noqa: F811
    resposta = _pedir(servir(AUMENTO, [24, 26]), sku='item B')

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert resposta.json()['codigo'] == 'modelo_indisponivel'


def test_chamada_e_gravada_uma_vez_no_historico(servir):  # noqa: F811
    cliente = servir(AUMENTO, [24, 26])

    corpo = _pedir(cliente).json()

    linhas, total = cliente.app.state.historico.consultar('item A', None)
    assert total == len(corpo['periodos'])
    assert {x.id_requisicao for x in linhas} == {corpo['id_requisicao']}


def test_rota_esta_no_swagger(servir):  # noqa: F811
    esquema = servir(AUMENTO, [24, 26]).get('/openapi.json').json()

    rota = esquema['paths']['/alertas/email']['post']
    assert set(rota['responses']) >= {'200', '404', '422', '503'}
    assert rota['description']
    assert 'envio_simulado' in rota['description']
