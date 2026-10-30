"""Explicação por template e por LLM (#20, Seam 3), sem chamar a rede.

O LLM é sempre substituído por uma função que devolve texto pronto.
"""

import json
from datetime import date

import pytest
from faker import Faker
from pydantic import ValidationError

from case_mr_health.config import Settings
from case_mr_health.explicacao import (
    EntradaExplicacao,
    criar_gerador_anthropic,
    explicar,
    montar_template,
    numeros_fora_da_entrada,
)

fake = Faker('pt_BR')


def entrada(**extra) -> EntradaExplicacao:
    base = {
        'sku': 'item A',
        'primeira_semana_prevista': date(2021, 8, 16),
        'vendas_4s': [14, 16, 18, 20],
        'previsao_2s': [24, 26],
        'limites_80': [(20.0, 28.0), (21.5, 30.5)],
        'media_vendida_4s': 17.0,
        'media_prevista_2s': 25.0,
        'variacao': 0.4706,
        'limite_aplicado': 0.3069,
        'n_variacoes_positivas': 6,
        'n_variacoes_negativas': 0,
        'resultado': 'aumento_significativo',
        'motivo': None,
    }
    return EntradaExplicacao(**{**base, **extra})


def llm_devolvendo(texto):
    return lambda _entrada: json.dumps({'texto': texto})


def test_template_traz_os_numeros_da_entrada():
    texto = montar_template(entrada())

    for esperado in ('17,0', '25,0', '47,1%', '30,7%', '24', '26'):
        assert esperado in texto
    assert 'item A' in texto
    assert 'pressão' in texto


@pytest.mark.parametrize(
    'resultado', ['aumento_significativo', 'reducao_significativa', 'estavel']
)
def test_template_nunca_fala_em_ruptura(resultado):
    texto = montar_template(entrada(resultado=resultado))

    assert 'ruptura' not in texto.lower()


def test_template_insuficiente_cita_o_motivo():
    texto = montar_template(
        entrada(
            resultado='insuficiente',
            motivo='variacoes_insuficientes',
            limite_aplicado=None,
        )
    )

    assert 'resultado da regra, insuficiente' in texto
    assert 'menos de 3 variações' in texto


def test_template_sem_venda_recente_nao_tem_variacao():
    texto = montar_template(
        entrada(
            vendas_4s=[0, 0, 0, 0],
            media_vendida_4s=0.0,
            variacao=None,
            limite_aplicado=None,
            resultado='insuficiente',
            motivo='sem_venda_recente',
        )
    )

    assert 'venda média das últimas 4 semanas é zero' in texto


def test_template_cita_estoque_so_quando_ha():
    sem = montar_template(entrada())
    com = montar_template(entrada(estoque=123.0))

    assert 'estoque atual' not in sem
    assert 'estoque atual é de 123' in com


@pytest.mark.parametrize('rodada', range(20))
def test_template_nao_tem_numero_fora_da_entrada(rodada):
    vendas = [fake.random_int(0, 500) for _ in range(4)]
    previsao = [fake.random_int(0, 500) for _ in range(2)]
    media_v = sum(vendas) / 4
    media_p = sum(previsao) / 2
    variacao = media_p / media_v - 1 if media_v else None
    dado = entrada(
        sku=fake.random_element(['item A', 'item B', 'item C', 'item D']),
        vendas_4s=vendas,
        previsao_2s=previsao,
        media_vendida_4s=media_v,
        media_prevista_2s=media_p,
        variacao=variacao,
        limite_aplicado=fake.random.random() if variacao else None,
        limites_80=[(p - 3.25, p + 3.25) for p in previsao],
        resultado='estavel' if variacao is not None else 'insuficiente',
        motivo=None if variacao is not None else 'sem_venda_recente',
        estoque=fake.random_int(0, 900) + 0.5,
    )

    assert numeros_fora_da_entrada(montar_template(dado), dado) == []


def test_detecta_numero_inventado():
    dado = entrada()

    assert numeros_fora_da_entrada('Vendeu 17,0 e 999 unidades.', dado) == [
        999.0
    ]


def test_aceita_arredondamento_e_data_da_entrada():
    dado = entrada()
    texto = 'Média 17 (47% acima) nas semanas de 16/08/2021, limite 30,7%.'

    assert numeros_fora_da_entrada(texto, dado) == []


def test_llm_valido_e_usado():
    texto = 'A previsão média é 25,0 contra 17,0 vendidos: pressão de alta.'

    resultado = explicar(entrada(), llm_devolvendo(texto))

    assert resultado.origem == 'llm'
    assert resultado.texto == texto


def test_sem_gerador_usa_template():
    resultado = explicar(entrada(), None)

    assert resultado.origem == 'template'
    assert resultado.texto == montar_template(entrada())


def test_falha_do_llm_cai_no_template():
    def falha(_entrada):
        raise TimeoutError('sem rede')

    resultado = explicar(entrada(), falha)

    assert resultado.origem == 'template'
    assert resultado.texto == montar_template(entrada())


@pytest.mark.parametrize(
    'bruto',
    [
        'isto não é json',
        json.dumps({'outro': 'campo'}),
        json.dumps({'texto': ''}),
        json.dumps({'texto': 'x' * 5000}),
        json.dumps({'texto': 'Há risco de ruptura do estoque.'}),
        json.dumps({'texto': 'Previsão de 25,0, estoque de 777 unidades.'}),
        json.dumps({'texto': 'Espere uma alta de 73 caixas.'}),
    ],
)
def test_saida_invalida_cai_no_template(bruto):
    resultado = explicar(entrada(), lambda _entrada: bruto)

    assert resultado.origem == 'template'
    assert resultado.texto == montar_template(entrada())


def test_saida_em_bloco_de_codigo_e_aceita():
    texto = 'Vendas de 17,0 e previsão de 25,0.'
    bruto = '```json\n' + json.dumps({'texto': texto}) + '\n```'

    resultado = explicar(entrada(), lambda _entrada: bruto)

    assert resultado.origem == 'llm'


def test_chave_ausente_nao_cria_gerador():
    cfg = Settings(_env_file=None, llm_api_key=None)

    assert criar_gerador_anthropic(cfg) is None


def test_chave_configurada_cria_gerador_sem_chamar_a_rede():
    cfg = Settings(_env_file=None, llm_api_key='chave-falsa')

    assert callable(criar_gerador_anthropic(cfg))


def test_modelo_e_chave_vem_da_configuracao(monkeypatch):
    monkeypatch.setenv('CASE_MR_HEALTH_LLM_MODELO', 'modelo-x')
    monkeypatch.setenv('CASE_MR_HEALTH_LLM_API_KEY', 'segredo')

    cfg = Settings(_env_file=None)

    assert cfg.llm_modelo == 'modelo-x'
    assert cfg.llm_api_key.get_secret_value() == 'segredo'
    assert 'segredo' not in repr(cfg)


def test_contrato_rejeita_resultado_desconhecido():
    with pytest.raises(ValidationError):
        entrada(resultado='ruptura_certa')
