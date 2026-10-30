"""Atualização de dados pela API (#30, ADR 0011): Seam 3 com TestClient.

Base sintética (planilhas do `conftest`), MLflow temporário e modelos
`naive`, que preveem o último valor da série. O reajuste roda de verdade em
segundo plano; só o teste de série com falha troca o reajuste por um dublê.
"""

import threading
import time
from datetime import date, timedelta
from io import BytesIO

import duckdb
import mlflow
import numpy as np
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient
from openpyxl import Workbook

from case_mr_health import algoritmos, intervalos
from case_mr_health.api.app import criar_app
from case_mr_health.api.servicos import atualizacao as servico
from case_mr_health.dados import preparar_dados
from case_mr_health.intervalos import ConfigIntervalos
from case_mr_health.treino import nome_modelo
from tests.test_api_predicao import registrar

HTTP_OK = 200
HTTP_ACEITO = 202
HTTP_NAO_ENCONTRADO = 404
HTTP_CONFLITO = 409
HTTP_INVALIDO = 422
CONFIG = ConfigIntervalos((0.80, 0.95), max_origens=5)
HORIZONTE = {'diaria': 14, 'semanal': 2}
PRIMEIRO_NOVO = 9_000_000_001
ULTIMO_VALOR_A = 4.0


def _xlsx(cabecalho: list, linhas: list[list]) -> bytes:
    wb = Workbook()
    wb.active.append([None, *cabecalho])
    for i, linha in enumerate(linhas):
        wb.active.append([i, *linha])
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def _arquivos(pedidos: list[tuple], itens: list[tuple]) -> dict:
    return {
        'pedidos': (
            'p.xlsx',
            _xlsx(
                ['ID_PEDIDO', 'DATA', 'VALOR_TOTAL'],
                [[*p, None] for p in pedidos],
            ),
        ),
        'itens': (
            'i.xlsx',
            _xlsx(
                ['ID_PEDIDO', 'ID_ITEM', 'QUANTIDADE'],
                [list(i) for i in itens],
            ),
        ),
    }


@pytest.fixture
def novos(planilhas):
    fim = max(date.fromisoformat(d) for _, d in planilhas.pedidos)
    dia1, dia2 = fim + timedelta(days=3), fim + timedelta(days=4)
    pedidos = [
        (PRIMEIRO_NOVO, f'{dia1:%Y-%m-%d}'),
        (PRIMEIRO_NOVO + 1, f'{dia2:%Y-%m-%d}'),
    ]
    itens = [
        (PRIMEIRO_NOVO, 'item A', 2),
        (PRIMEIRO_NOVO, 'item A', 3),
        (PRIMEIRO_NOVO + 1, 'item A', int(ULTIMO_VALOR_A)),
    ]
    return pedidos, itens, dia2


@pytest.fixture
def cfg(settings, tmp_path):
    preparar_dados(settings)
    cfg = settings.model_copy(
        update={
            'mlflow_tracking_uri': f'sqlite:///{tmp_path / "mlflow.db"}',
            'mlflow_artifact_dir': tmp_path / 'artefatos',
            'historico_db_path': tmp_path / 'servico' / 'h.duckdb',
            'atualizacoes_dir': tmp_path / 'copias',
            'modelos_fixados': {},
        }
    )
    y = np.random.default_rng(3).integers(1, 20, 30).astype(float)
    for gran in ('diaria', 'semanal'):
        previsor = algoritmos.criar('naive', {}, 1).ajustar(y)
        calibracao = intervalos.calibrar(
            lambda: algoritmos.criar('naive', {}, 1),
            y,
            HORIZONTE[gran],
            CONFIG,
        )
        registrado = registrar(
            cfg,
            'item A',
            gran,
            previsor,
            calibracao,
            tags_run={'algoritmo': 'naive'},
            tags_versao={
                'algoritmo': 'naive',
                'hiperparametros': '{}',
                'intervalo_metodo': calibracao.metodo,
            },
        )
        MlflowClient().log_param(registrado.run_id, 'seed', 1)
    return cfg


@pytest.fixture
def cliente(cfg):
    with TestClient(criar_app(cfg)) as c:
        yield c


def _esperar(cliente, id_atualizacao: str, tempo: float = 60.0) -> dict:
    limite = time.monotonic() + tempo
    while time.monotonic() < limite:
        corpo = cliente.get(f'/dados/atualizacoes/{id_atualizacao}').json()
        if corpo['estado'] != 'em_andamento':
            return corpo
        time.sleep(0.1)
    pytest.fail('a atualização não terminou')


def _por_serie(corpo: dict) -> dict:
    return {(s['sku'], s['granularidade']): s for s in corpo['series']}


def _champion(cfg, sku, gran) -> str:
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    versao = MlflowClient().get_model_version_by_alias(
        nome_modelo(sku, gran), 'champion'
    )
    return str(versao.version)


def test_envio_valido_responde_202_e_conclui(cliente, novos):
    pedidos, itens, dia2 = novos

    resposta = cliente.post('/dados/pedidos', files=_arquivos(pedidos, itens))

    assert resposta.status_code == HTTP_ACEITO
    corpo = resposta.json()
    assert corpo['estado'] == 'em_andamento'
    assert (corpo['pedidos_novos'], corpo['itens_novos']) == (2, 2)
    assert corpo['ultimo_dia'] == str(dia2)
    assert 'fora da amostra' in corpo['aviso']
    final = _esperar(cliente, corpo['id'])
    assert final['estado'] == 'concluida'
    assert final['concluida_em'] is not None


def test_series_com_versao_servida_sao_reajustadas_e_as_demais_ignoradas(
    cliente, novos
):
    pedidos, itens, _ = novos
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']

    series = _por_serie(_esperar(cliente, id_))

    for gran in ('diaria', 'semanal'):
        assert series['item A', gran]['estado'] == 'reajustada'
        assert series['item A', gran]['servida'] is True
        assert series['item A', gran]['versao_anterior'] == '1'
    assert series['item B', 'diaria']['estado'] == 'ignorada'
    assert len(series) == len(('item A', 'item B', 'item C', 'item D')) * 2


def test_api_passa_a_servir_a_versao_nova_sem_reiniciar(cliente, novos):
    pedidos, itens, dia2 = novos
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']
    _esperar(cliente, id_)

    resposta = cliente.post(
        '/predicoes',
        json={
            'sku': 'item A',
            'granularidade': 'diaria',
            'data_referencia': str(dia2),
        },
    )

    assert resposta.status_code == HTTP_OK
    corpo = resposta.json()
    assert corpo['versao_modelo'] == '2'
    assert corpo['origem_modelo'] == 'atualizacao'
    assert corpo['periodos'][0]['quantidade_prevista'] == ULTIMO_VALOR_A


def test_grafico_da_serie_inclui_os_pedidos_novos(cliente, novos):
    pedidos, itens, dia2 = novos
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']
    _esperar(cliente, id_)

    pontos = cliente.get('/series/item A/diaria').json()

    assert pontos['pontos'][-1]['data'] == str(dia2)
    assert pontos['pontos'][-1]['quantidade'] == ULTIMO_VALOR_A


def test_versoes_listam_origem_e_versao_anterior(cliente, novos):
    pedidos, itens, _ = novos
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']
    _esperar(cliente, id_)

    modelos = cliente.get('/modelos').json()['modelos']

    nova = next(
        m
        for m in modelos
        if (m['sku'], m['granularidade'], m['versao'])
        == ('item A', 'diaria', '2')
    )
    assert nova['origem'] == 'atualizacao'
    assert nova['versao_anterior'] == '1'
    assert nova['champion'] is True


def test_planilha_invalida_responde_422_com_planilha_e_linha(cliente, novos):
    pedidos, itens, _ = novos
    itens = [*itens[:1], (PRIMEIRO_NOVO, 'item Z', 1), *itens[1:]]

    resposta = cliente.post('/dados/pedidos', files=_arquivos(pedidos, itens))

    assert resposta.status_code == HTTP_INVALIDO
    corpo = resposta.json()
    assert corpo['codigo'] == 'dados_invalidos'
    assert corpo['detalhes'][0]['campo'] == 'ITEM_PEDIDO linha 3'
    assert 'item Z' in corpo['detalhes'][0]['mensagem']


def test_erro_nao_aplica_nada_e_nao_trava_a_proxima_atualizacao(
    cliente, novos
):
    pedidos, itens, _ = novos
    ruim = [*itens, (PRIMEIRO_NOVO, 'item Z', 1)]
    assert (
        cliente.post(
            '/dados/pedidos', files=_arquivos(pedidos, ruim)
        ).status_code
        == HTTP_INVALIDO
    )

    resposta = cliente.post('/dados/pedidos', files=_arquivos(pedidos, itens))

    assert resposta.status_code == HTTP_ACEITO
    _esperar(cliente, resposta.json()['id'])


def test_arquivo_que_nao_e_xlsx_responde_422(cliente):
    resposta = cliente.post(
        '/dados/pedidos',
        files={
            'pedidos': ('p.xlsx', b'nao e planilha'),
            'itens': ('i.xlsx', b'x'),
        },
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['detalhes'][0]['campo'] == 'arquivo'


def test_campo_ausente_responde_422(cliente, novos):
    pedidos, itens, _ = novos
    arquivos = _arquivos(pedidos, itens)
    del arquivos['itens']

    resposta = cliente.post('/dados/pedidos', files=arquivos)

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['detalhes'][0]['campo'] == 'itens'


def test_mesmo_par_de_arquivos_nao_e_aplicado_duas_vezes(cliente, novos):
    pedidos, itens, _ = novos
    arquivos = _arquivos(pedidos, itens)
    id_ = cliente.post('/dados/pedidos', files=arquivos).json()['id']
    _esperar(cliente, id_)

    resposta = cliente.post('/dados/pedidos', files=arquivos)

    assert resposta.status_code == HTTP_CONFLITO
    assert resposta.json()['codigo'] == 'atualizacao_recusada'


def test_pedidos_ja_na_base_sao_recusados_com_a_linha(cliente, novos):
    pedidos, itens, _ = novos
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']
    _esperar(cliente, id_)

    # Mesmo conteúdo em outro arquivo (outro hash): o pedido já existe.
    resposta = cliente.post('/dados/pedidos', files=_arquivos(pedidos, itens))

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['detalhes'][0]['campo'] == 'PEDIDO linha 2'


def test_segunda_atualizacao_durante_o_reajuste_e_recusada(
    cliente, novos, monkeypatch
):
    pedidos, itens, _ = novos
    liberar, chegou = threading.Event(), threading.Event()

    def preso(*_):
        chegou.set()
        liberar.wait(30)
        raise servico.SemVersao('dublê')

    monkeypatch.setattr(servico, 'reajustar_serie', preso)
    primeira = cliente.post('/dados/pedidos', files=_arquivos(pedidos, itens))
    assert chegou.wait(30)
    outros = (
        [(PRIMEIRO_NOVO + 5, '2021-12-01')],
        [(PRIMEIRO_NOVO + 5, 'item A', 1)],
    )

    recusada = cliente.post('/dados/pedidos', files=_arquivos(*outros))

    assert recusada.status_code == HTTP_CONFLITO
    assert 'em andamento' in recusada.json()['mensagem']
    liberar.set()
    _esperar(cliente, primeira.json()['id'])
    aceita = cliente.post('/dados/pedidos', files=_arquivos(*outros))
    assert aceita.status_code == HTTP_ACEITO
    _esperar(cliente, aceita.json()['id'])


def test_falha_numa_serie_nao_derruba_as_outras(
    cfg, cliente, novos, monkeypatch
):
    pedidos, itens, _ = novos
    original = servico.reajustar_serie

    def falha_na_semanal(cfg_, sku, gran, hash_):
        if (sku, gran) == ('item A', 'semanal'):
            raise RuntimeError('ajuste não convergiu')
        return original(cfg_, sku, gran, hash_)

    monkeypatch.setattr(servico, 'reajustar_serie', falha_na_semanal)
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']

    final = _esperar(cliente, id_)

    series = _por_serie(final)
    assert final['estado'] == 'concluida_com_erros'
    assert series['item A', 'diaria']['estado'] == 'reajustada'
    assert series['item A', 'semanal']['estado'] == 'falhou'
    assert 'não convergiu' in series['item A', 'semanal']['erro']
    assert _champion(cfg, 'item A', 'semanal') == '1'
    assert _champion(cfg, 'item A', 'diaria') == '2'


def test_atualizacao_desconhecida_responde_404(cliente):
    resposta = cliente.get('/dados/atualizacoes/nao-existe')

    assert resposta.status_code == HTTP_NAO_ENCONTRADO
    assert resposta.json()['codigo'] == 'atualizacao_inexistente'


def test_rotas_estao_no_swagger(cliente):
    esquema = cliente.get('/openapi.json').json()

    envio = esquema['paths']['/dados/pedidos']['post']
    assert set(envio['responses']) >= {'202', '409', '422'}
    assert envio['description']
    assert '/dados/atualizacoes/{id_atualizacao}' in esquema['paths']


def test_base_original_so_cresce(cfg, cliente, novos):
    pedidos, itens, _ = novos
    with duckdb.connect(str(cfg.db_path), read_only=True) as con:
        antes = con.execute('SELECT count(*) FROM pedido').fetchone()[0]
    id_ = cliente.post(
        '/dados/pedidos', files=_arquivos(pedidos, itens)
    ).json()['id']
    _esperar(cliente, id_)

    with duckdb.connect(str(cfg.db_path), read_only=True) as con:
        depois = con.execute('SELECT count(*) FROM pedido').fetchone()[0]
    assert depois == antes + len(pedidos)
