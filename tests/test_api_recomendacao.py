"""Recomendação determinística (#19): regra pura e rota (Seam 3).

Os casos 1 a 5 são os exemplos aprovados no #18. Na rota, o modelo semanal
é um `naive_sazonal` de período 2 cuja série termina nas duas semanas que a
regra deve receber como previsão.
"""

from contextlib import ExitStack
from datetime import date, timedelta

import duckdb
import numpy as np
import pytest
from fastapi.testclient import TestClient

from case_mr_health import algoritmos, intervalos, recomendacao
from case_mr_health.api.app import criar_app
from case_mr_health.config import Settings
from case_mr_health.intervalos import ConfigIntervalos
from case_mr_health.recomendacao import recomendar
from tests.test_api_predicao import registrar

HTTP_OK = 200
HTTP_NAO_ENCONTRADO = 404
HTTP_INDISPONIVEL = 503
ULTIMA_SEMANA = date(2021, 8, 9)  # segunda-feira da última semana do treino
CONFIG = ConfigIntervalos((0.80, 0.95), max_origens=5)
AVISO = 'baixa confiabilidade estatística: poucas janelas históricas'

AUMENTO = [10, 12, 8, 10, 14, 10, 12, 16, 14, 18, 16, 20]
REDUCAO = [20, 18, 22, 20, 16, 18, 14, 16, 12, 14, 10, 12]
SEM_VENDA = [5, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0]
POUCAS_POSITIVAS = [20, 18, 22, 20, 16, 18, 14, 16, 12, 14, 10, 10]

CASOS = {
    'aumento': (
        AUMENTO,
        [24, 26],
        ('aumento_significativo', None, 0.4706, 0.3069, 6, 0),
    ),
    'reducao': (
        REDUCAO,
        [7, 9],
        ('reducao_significativa', None, -0.3333, 0.2053, 0, 7),
    ),
    'estavel': (
        AUMENTO,
        [17, 19],
        ('estavel', None, 0.0588, 0.3069, 6, 0),
    ),
    'sem_venda_recente': (
        SEM_VENDA,
        [2, 2],
        ('insuficiente', 'sem_venda_recente', None, None, 0, 3),
    ),
    'variacoes_insuficientes': (
        POUCAS_POSITIVAS,
        [16, 18],
        ('insuficiente', 'variacoes_insuficientes', 0.4783, None, 0, 7),
    ),
}


# --- regra pura -----------------------------------------------------------


@pytest.mark.parametrize(('vendas', 'previsao', 'esperado'), CASOS.values())
def test_casos_aprovados_no_18(vendas, previsao, esperado):
    resultado, motivo, variacao, limite, positivas, negativas = esperado

    obtida = recomendar(vendas, previsao)

    assert obtida.resultado == resultado
    assert obtida.motivo == motivo
    assert obtida.variacao == pytest.approx(variacao, abs=1e-4)
    assert obtida.limite_aplicado == pytest.approx(limite, abs=1e-4)
    assert obtida.n_variacoes_positivas == positivas
    assert obtida.n_variacoes_negativas == negativas


def test_variacoes_historicas_do_caso_1():
    variacoes = recomendacao.variacoes_historicas(AUMENTO)

    esperadas = [0.2, 0.0, 0.3333, 0.3043, 0.2308, 0.3077, 0.2]
    assert variacoes == pytest.approx(esperadas, abs=1e-4)


def test_variacao_igual_ao_limite_e_estavel():
    # Três janelas com base 8 e seguintes 16: o Q3 é 1,0, e a base atual
    # (16) com previsão média 32 dá exatamente 1,0.
    vendas = [0, 32, 0, 0, 0, 32, 0, 32]

    no_limite = recomendar(vendas, [32, 32])
    acima = recomendar(vendas, [33, 33])

    assert no_limite.variacao == no_limite.limite_aplicado
    assert no_limite.resultado == 'estavel'
    assert acima.resultado == 'aumento_significativo'


def test_variacao_zero_e_estavel_sem_exigir_minimo():
    obtida = recomendar([5, 5, 5, 5], [5, 5])

    assert obtida.resultado == 'estavel'
    assert obtida.motivo is None
    assert obtida.variacao == 0
    assert obtida.limite_aplicado is None


def test_janela_com_base_zero_nao_conta_como_positiva_nem_negativa():
    vendas = [0, 0, 0, 0, 3, 3, 10, 10, 10, 10, 20, 20]

    variacoes = recomendacao.variacoes_historicas(vendas)

    # Só as janelas com base diferente de zero entram.
    assert all(np.isfinite(variacoes))
    assert len(variacoes) == len(vendas) - 6 + 1 - 1


def test_lado_oposto_nao_influencia():
    # Caso 5 tem 7 negativas, mas a variação atual é positiva.
    obtida = recomendar(POUCAS_POSITIVAS, [16, 18])

    assert obtida.motivo == 'variacoes_insuficientes'


@pytest.mark.parametrize('previsao', [[1], [1, 2, 3]])
def test_exige_duas_semanas_previstas(previsao):
    with pytest.raises(ValueError, match='semanas previstas'):
        recomendar([1, 2, 3, 4], previsao)


def test_exige_quatro_semanas_de_venda():
    with pytest.raises(ValueError, match='semanas de venda'):
        recomendar([1, 2, 3], [1, 2])


# --- rota -----------------------------------------------------------------


def _semanas(vendas: list[int]) -> list[tuple[str, date, float]]:
    inicio = ULTIMA_SEMANA - timedelta(weeks=len(vendas) - 1)
    linhas = [
        ('item A', inicio + timedelta(weeks=i), float(q))
        for i, q in enumerate(vendas)
    ]
    # Semana depois do treino: a rota não pode usá-la.
    return [*linhas, ('item A', ULTIMA_SEMANA + timedelta(weeks=1), 999.0)]


def _configuracao(raiz, vendas: list[int]) -> Settings:
    caminho = raiz / 'desenvolvimento.duckdb'
    with duckdb.connect(str(caminho)) as con:
        con.execute(
            'CREATE TABLE serie_semanal '
            '(sku VARCHAR, semana DATE, quantidade DOUBLE)'
        )
        con.executemany(
            'INSERT INTO serie_semanal VALUES (?, ?, ?)', _semanas(vendas)
        )
    return Settings(
        _env_file=None,
        mlflow_tracking_uri=f'sqlite:///{raiz / "mlflow.db"}',
        mlflow_artifact_dir=raiz / 'artefatos',
        historico_db_path=raiz / 'servico' / 'historico.duckdb',
        desenvolvimento_db_path=caminho,
        modelos_fixados={},
    )


def _registrar_semanal(cfg: Settings, previsao: list[int]) -> None:
    rng = np.random.default_rng(len(previsao) + int(sum(previsao)))
    y = np.array([*rng.integers(1, 40, 28).astype(float), *previsao])
    hp = {'periodo': 2}
    previsor = algoritmos.criar('naive_sazonal', hp, 1).ajustar(y)
    calibracao = intervalos.calibrar(
        lambda: algoritmos.criar('naive_sazonal', hp, 1),
        y,
        recomendacao.SEMANAS_PREVISTAS,
        CONFIG,
    )
    registrar(cfg, 'item A', 'semanal', previsor, calibracao)


@pytest.fixture
def servir(tmp_path):
    with ExitStack() as pilha:

        def _servir(vendas, previsao) -> TestClient:
            cfg = _configuracao(tmp_path, vendas)
            _registrar_semanal(cfg, previsao)
            return pilha.enter_context(TestClient(criar_app(cfg)))

        yield _servir


@pytest.mark.parametrize(('vendas', 'previsao', 'esperado'), CASOS.values())
def test_rota_devolve_a_regra_do_18(servir, vendas, previsao, esperado):
    resultado, motivo, variacao, limite, positivas, negativas = esperado
    cliente = servir(vendas, previsao)

    resposta = cliente.get('/recomendacoes/item A')

    assert resposta.status_code == HTTP_OK
    corpo = resposta.json()
    assert corpo['resultado'] == resultado
    assert corpo['motivo'] == motivo
    assert corpo['variacao'] == pytest.approx(variacao, abs=1e-4)
    assert corpo['limite_aplicado'] == pytest.approx(limite, abs=1e-4)
    assert corpo['n_variacoes_positivas'] == positivas
    assert corpo['n_variacoes_negativas'] == negativas
    assert corpo['media_vendida_4s'] == pytest.approx(np.mean(vendas[-4:]))
    assert corpo['media_prevista_2s'] == pytest.approx(np.mean(previsao))
    assert corpo['granularidade'] == 'semanal'
    assert corpo['nivel'] == 'rede'


@pytest.mark.parametrize(('vendas', 'previsao', 'esperado'), CASOS.values())
def test_toda_resposta_traz_aviso_e_vocabulario(
    servir, vendas, previsao, esperado
):
    cliente = servir(vendas, previsao)

    corpo = cliente.get('/recomendacoes/item A').json()

    assert corpo['aviso'] == AVISO
    assert 'pressão' in corpo['texto']
    assert 'estoque' in corpo['texto']
    assert 'ruptura' not in corpo['texto'].lower()
    assert 'confiança' not in corpo


def test_texto_dos_resultados_significativos(servir):
    alta = servir(AUMENTO, [24, 26]).get('/recomendacoes/item A').json()

    assert 'pressão de alta sobre o estoque' in alta['texto']
    assert 'limite histórico de 30,7%' in alta['texto']


def test_texto_de_reducao(servir):
    baixa = servir(REDUCAO, [7, 9]).get('/recomendacoes/item A').json()

    assert 'pressão de baixa sobre o estoque' in baixa['texto']


def test_semana_depois_do_treino_nao_entra_na_base(servir):
    # A semana de 999 unidades está depois do fim do treino.
    cliente = servir(AUMENTO, [24, 26])

    corpo = cliente.get('/recomendacoes/item A').json()

    assert corpo['media_vendida_4s'] == pytest.approx(17.0)


def test_chamada_e_gravada_no_historico(servir):
    cliente = servir(AUMENTO, [24, 26])

    corpo = cliente.get('/recomendacoes/item A').json()

    linhas, total = cliente.app.state.historico.consultar('item A', 'semanal')
    assert total == recomendacao.SEMANAS_PREVISTAS
    assert {linha.id_requisicao for linha in linhas} == {
        corpo['id_requisicao']
    }
    assert sorted(linha.quantidade_prevista for linha in linhas) == [24, 26]
    assert {linha.recomendacao for linha in linhas} == {corpo['resultado']}
    assert {linha.versao_modelo for linha in linhas} == {
        corpo['versao_modelo']
    }
    assert {linha.hash_artefato for linha in linhas} == {
        corpo['hash_artefato']
    }


def test_resposta_traz_versao_e_hash_do_modelo(servir):
    cliente = servir(AUMENTO, [24, 26])

    corpo = cliente.get('/recomendacoes/item A').json()

    modelo = cliente.app.state.modelos.obter('item A', 'semanal')
    assert corpo['versao_modelo'] == modelo.versao
    assert corpo['hash_artefato'] == modelo.hash_artefato


def test_sku_inexistente_responde_404(servir):
    cliente = servir(AUMENTO, [24, 26])

    resposta = cliente.get('/recomendacoes/item Z')

    assert resposta.status_code == HTTP_NAO_ENCONTRADO
    assert resposta.json()['codigo'] == 'sku_inexistente'


def test_sku_sem_modelo_semanal_responde_503(servir):
    cliente = servir(AUMENTO, [24, 26])

    resposta = cliente.get('/recomendacoes/item B')

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert resposta.json()['codigo'] == 'modelo_indisponivel'
    linhas, total = cliente.app.state.historico.consultar('item B', None)
    assert (linhas, total) == ([], 0)


def test_rota_esta_no_swagger(servir):
    cliente = servir(AUMENTO, [24, 26])

    esquema = cliente.get('/openapi.json').json()

    rota = esquema['paths']['/recomendacoes/{sku}']['get']
    assert set(rota['responses']) >= {'200', '404', '503'}
    assert rota['description']
