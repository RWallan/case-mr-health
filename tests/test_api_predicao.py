"""Seam 3 da predição individual (#14): TestClient e MLflow temporário.

Os modelos são registrados como o treino registra (mesma sequência de
`log_model`, hash e tags), mas com previsores leves e séries sintéticas.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb
import mlflow
import mlflow.pyfunc
import numpy as np
import pytest
from faker import Faker
from fastapi.testclient import TestClient
from loguru import logger
from mlflow import MlflowClient

import case_mr_health.cli as modulo_cli
from case_mr_health import algoritmos, intervalos, treino
from case_mr_health.api.app import criar_app
from case_mr_health.api.erros import HistoricoIndisponivel
from case_mr_health.api.historico import Historico
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.intervalos import Calibracao, ConfigIntervalos
from case_mr_health.particoes import GRANULARIDADES
from case_mr_health.treino import (
    CAMINHO_MODELO,
    ModeloDemanda,
    hash_artefato,
    nome_experimento,
    nome_modelo,
)

FIM_DIARIA = date(2021, 8, 18)  # quarta-feira
FIM_SEMANAL = date(2021, 8, 15)  # domingo
SEGUNDA_FINAL = date(2021, 8, 9)
HORIZONTE_DIARIO = 14
HORIZONTE_SEMANAL = 2
CONFIG = ConfigIntervalos((0.80, 0.95), max_origens=5)
NAN = float('nan')
HTTP_OK = 200
HTTP_NAO_ENCONTRADO = 404
HTTP_INVALIDO = 422
HTTP_INDISPONIVEL = 503


def _fim(granularidade: str) -> date:
    return FIM_DIARIA if granularidade == 'diaria' else FIM_SEMANAL


def _horizonte(granularidade: str) -> int:
    if granularidade == 'diaria':
        return HORIZONTE_DIARIO
    return HORIZONTE_SEMANAL


def _serie(ultimo: float, n: int = 30) -> np.ndarray:
    fake = Faker('pt_BR')
    Faker.seed(int(ultimo))
    valores = [float(fake.random_int(1, 40)) for _ in range(n - 1)]
    return np.array([*valores, ultimo])


def _previsor(algoritmo: str, hp: dict, y: np.ndarray):
    return algoritmos.criar(algoritmo, hp, 1).ajustar(y)


def _calibrar(algoritmo, hp, y, granularidade) -> Calibracao:
    return intervalos.calibrar(
        lambda: algoritmos.criar(algoritmo, hp, 1),
        y,
        _horizonte(granularidade),
        CONFIG,
    )


def _sem_intervalo(granularidade: str) -> Calibracao:
    return Calibracao(
        intervalos.INDISPONIVEL,
        CONFIG.niveis,
        _horizonte(granularidade),
        dict.fromkeys(CONFIG.niveis, (NAN, NAN)),
    )


@dataclass(frozen=True)
class Registrado:
    versao: str
    hash: str
    run_id: str
    experimento_id: str


def registrar(  # noqa: PLR0913, PLR0917
    cfg: Settings,
    sku: str,
    granularidade: str,
    previsor,
    calibracao: Calibracao | None,
    tags_run: dict | None = None,
    tags_versao: dict | None = None,
    champion: bool = True,
) -> Registrado:
    """Mesma sequência de `treino._treinar_candidato`, com menos metadados."""
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    nome_exp = nome_experimento(granularidade)
    experimento = mlflow.get_experiment_by_name(nome_exp)
    if experimento is None:
        experimento_id = mlflow.create_experiment(
            nome_exp, artifact_location=cfg.mlflow_artifact_dir.as_uri()
        )
    else:
        experimento_id = experimento.experiment_id
    nome = nome_modelo(sku, granularidade)
    cliente = MlflowClient()
    with mlflow.start_run(experiment_id=experimento_id) as run:
        mlflow.set_tags({
            'sku': sku,
            'granularidade': granularidade,
            'algoritmo': 'naive',
            **(tags_run or {}),
        })
        mlflow.log_params({
            'desenvolvimento_fim': _fim(granularidade),
            'oot_fim': _fim(granularidade) + timedelta(days=14),
        })
        info = mlflow.pyfunc.log_model(
            name=CAMINHO_MODELO,
            python_model=ModeloDemanda(previsor, calibracao),
            registered_model_name=nome,
            pip_requirements=treino.requisitos_pip(previsor),
        )
        artefato = Path(mlflow.artifacts.download_artifacts(info.model_uri))
        hash_modelo = hash_artefato(artefato)
    versao = str(info.registered_model_version)
    for chave, valor in {
        'hash_artefato': hash_modelo,
        'run_id': run.info.run_id,
        **(tags_versao or {}),
    }.items():
        cliente.set_model_version_tag(nome, versao, chave, valor)
    if champion:
        cliente.set_registered_model_alias(nome, 'champion', versao)
    return Registrado(versao, hash_modelo, run.info.run_id, experimento_id)


def naive(
    cfg, sku, granularidade, ultimo, *, calibracao=None, **kwargs
) -> Registrado:
    y = _serie(ultimo)
    return registrar(
        cfg,
        sku,
        granularidade,
        _previsor('naive', {}, y),
        calibracao or _calibrar('naive', {}, y, granularidade),
        **kwargs,
    )


@pytest.fixture(scope='module')
def base(tmp_path_factory) -> Settings:
    raiz = tmp_path_factory.mktemp('api')
    return Settings(
        _env_file=None,
        mlflow_tracking_uri=f'sqlite:///{raiz / "mlflow.db"}',
        mlflow_artifact_dir=raiz / 'artefatos',
        historico_db_path=raiz / 'servico' / 'historico.duckdb',
        modelos_fixados={},
    )


@pytest.fixture(scope='module')
def registro(base) -> dict[tuple[str, str], Registrado]:
    """Cada série tem um último valor próprio, que a identifica na resposta.

    - item A: as duas granularidades com champion, e a diária tem uma
      versão mais nova que não é champion;
    - item B: diária sazonal (cada passo prevê um valor) e semanal sem
      intervalos;
    - item C: nenhum champion;
    - item D: só a semanal tem champion.
    """
    sazonal = {'periodo': 7}
    y_b = np.array([float(i) for i in (1, 2, 3, 4, 5, 6, 7)] * 4)
    versoes = {
        ('item A', 'diaria'): naive(
            base,
            'item A',
            'diaria',
            11.0,
        ),
        ('item A', 'semanal'): naive(base, 'item A', 'semanal', 70.0),
        ('item B', 'diaria'): registrar(
            base,
            'item B',
            'diaria',
            _previsor('naive_sazonal', sazonal, y_b),
            _calibrar('naive_sazonal', sazonal, y_b, 'diaria'),
        ),
        ('item B', 'semanal'): naive(
            base,
            'item B',
            'semanal',
            90.0,
            calibracao=_sem_intervalo('semanal'),
        ),
        ('item D', 'semanal'): naive(base, 'item D', 'semanal', 44.0),
    }
    versoes['item A nova'] = naive(
        base, 'item A', 'diaria', 12.0, champion=False
    )
    naive(base, 'item D', 'diaria', 33.0, champion=False)
    return versoes


@pytest.fixture(scope='module')
def cliente(base, registro):
    with TestClient(criar_app(base)) as c:
        yield c


def _app_com(base: Settings, destino: Path, **ajustes) -> TestClient:
    cfg = base.model_copy(
        update={'historico_db_path': destino / 'h.duckdb', **ajustes}
    )
    return TestClient(criar_app(cfg))


def _pedir(cliente, sku='item A', granularidade='diaria', **campos):
    corpo = {
        'sku': sku,
        'granularidade': granularidade,
        'data_referencia': str(_fim(granularidade)),
        **campos,
    }
    return cliente.post('/predicoes', json=corpo)


def _detalhes(resposta) -> dict[str, str]:
    return {d['campo']: d['mensagem'] for d in resposta.json()['detalhes']}


# --- resposta -----------------------------------------------------------


def test_resposta_traz_o_contrato_completo(cliente, registro):
    esperado = registro['item A', 'diaria']

    resposta = _pedir(cliente)

    assert resposta.status_code == HTTP_OK
    corpo = resposta.json()
    periodo = corpo['periodos'][0]
    assert corpo['sku'] == 'item A'
    assert corpo['granularidade'] == 'diaria'
    assert corpo['nivel'] == 'rede'
    assert corpo['valor_unitario'] == pytest.approx(10)
    assert corpo['versao_modelo'] == esperado.versao
    assert corpo['hash_artefato'] == esperado.hash
    assert corpo['run_id'] == esperado.run_id
    assert corpo['experimento_id'] == esperado.experimento_id
    assert corpo['data_geracao'].endswith('-03:00')
    assert len(corpo['periodos']) == 1
    assert periodo['data_alvo'] == str(FIM_DIARIA + timedelta(days=1))
    assert periodo['quantidade_prevista'] == pytest.approx(11)
    assert periodo['valor_previsto'] == pytest.approx(110)
    assert (
        periodo['limite_inferior_95']
        <= periodo['limite_inferior_80']
        <= periodo['quantidade_prevista']
        <= periodo['limite_superior_80']
        <= periodo['limite_superior_95']
    )


def test_resposta_nao_traz_confianca(cliente):
    assert 'confianca' not in _pedir(cliente).json()


@pytest.mark.parametrize('sku', ['A', 'a', 'item a', ' item A '])
def test_sku_aceita_a_letra(cliente, sku):
    assert _pedir(cliente, sku=sku).json()['sku'] == 'item A'


def test_limites_nan_viram_null(cliente):
    corpo = _pedir(cliente, 'item B', 'semanal').json()
    periodo = corpo['periodos'][0]

    assert periodo['quantidade_prevista'] == pytest.approx(90)
    for nivel in ('inferior_80', 'superior_80', 'inferior_95', 'superior_95'):
        assert periodo[f'limite_{nivel}'] is None


# --- seleção ------------------------------------------------------------


@pytest.mark.parametrize(
    ('sku', 'granularidade', 'quantidade', 'valor_unitario'),
    [
        ('item A', 'diaria', 11, 10),
        ('item A', 'semanal', 70, 10),
        ('item B', 'semanal', 90, 15),
        ('item D', 'semanal', 44, 25),
    ],
)
def test_seleciona_o_modelo_da_serie_pedida(  # noqa: PLR0913, PLR0917
    cliente, registro, sku, granularidade, quantidade, valor_unitario
):
    corpo = _pedir(cliente, sku, granularidade).json()

    assert corpo['run_id'] == registro[sku, granularidade].run_id
    assert corpo['periodos'][0]['quantidade_prevista'] == pytest.approx(
        quantidade
    )
    assert corpo['valor_unitario'] == pytest.approx(valor_unitario)


def test_champion_tem_precedencia_sobre_a_versao_mais_nova(cliente, registro):
    nova = registro['item A nova']

    corpo = _pedir(cliente).json()

    assert corpo['versao_modelo'] != nova.versao
    assert corpo['periodos'][0]['quantidade_prevista'] == pytest.approx(11)


def test_versao_fixada_substitui_o_champion(base, registro, tmp_path):
    nova = registro['item A nova']
    fixados = {nome_modelo('item A', 'diaria'): nova.versao}

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        corpo = _pedir(c).json()

    assert corpo['versao_modelo'] == nova.versao
    assert corpo['periodos'][0]['quantidade_prevista'] == pytest.approx(12)


def test_semanal_nao_usa_modelo_diario_e_vice_versa(base, registro, tmp_path):
    """item D só tem a semanal; com a fixação, item A só tem a diária."""
    fixados = {nome_modelo('item A', 'semanal'): '999'}

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        assert _pedir(c, 'item D', 'diaria').status_code == HTTP_INDISPONIVEL
        assert _pedir(c, 'item D', 'semanal').status_code == HTTP_OK
        assert _pedir(c, 'item A', 'semanal').status_code == HTTP_INDISPONIVEL
        assert _pedir(c, 'item A', 'diaria').status_code == HTTP_OK


def test_versao_de_outra_granularidade_e_recusada(base, registro, tmp_path):
    """Mesmo registrada no nome certo, não serve outra granularidade."""
    trocada = naive(
        base,
        'item C',
        'semanal',
        50.0,
        tags_run={'granularidade': 'diaria'},
        champion=False,
    )
    fixados = {nome_modelo('item C', 'semanal'): trocada.versao}

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        resposta = _pedir(c, 'item C', 'semanal')

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert resposta.json()['codigo'] == 'modelo_indisponivel'


# --- indisponibilidade --------------------------------------------------


def test_serie_sem_champion_responde_503_e_api_sobe(cliente):
    resposta = _pedir(cliente, 'item C', 'diaria')

    assert resposta.status_code == HTTP_INDISPONIVEL
    corpo = resposta.json()
    assert corpo['codigo'] == 'modelo_indisponivel'
    assert 'item C/diaria' in corpo['mensagem']
    assert 'champion' in corpo['mensagem']


def test_versao_fixada_inexistente_nao_recai_no_champion(
    base, registro, tmp_path
):
    fixados = {nome_modelo('item A', 'diaria'): '999'}

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        assert _pedir(c).status_code == HTTP_INDISPONIVEL
        assert _pedir(c, granularidade='semanal').status_code == HTTP_OK


def test_mlflow_inacessivel_nao_derruba_a_api(base, tmp_path):
    with _app_com(
        base,
        tmp_path,
        mlflow_tracking_uri=f'sqlite:///{tmp_path / "x" / "y" / "m.db"}',
    ) as c:
        assert _pedir(c).status_code == HTTP_INDISPONIVEL
    mlflow.set_tracking_uri(base.mlflow_tracking_uri)


def test_modelo_sem_calibracao_fica_indisponivel(base, registro, tmp_path):
    sem_calibracao = registrar(
        base,
        'item C',
        'diaria',
        _previsor('naive', {}, _serie(50.0)),
        None,
        champion=False,
    )
    fixados = {nome_modelo('item C', 'diaria'): sem_calibracao.versao}

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        resposta = _pedir(c, 'item C', 'diaria')

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert 'calibração' in resposta.json()['mensagem']


# --- hash ---------------------------------------------------------------


@pytest.fixture
def erros_logados():
    mensagens = []
    sink = logger.add(mensagens.append, level='ERROR', format='{message}')
    yield mensagens
    logger.remove(sink)


def _versao_nova_item_d(base) -> tuple[Registrado, dict]:
    nova = naive(base, 'item D', 'diaria', 34.0, champion=False)
    return nova, {nome_modelo('item D', 'diaria'): nova.versao}


def test_tag_de_hash_divergente_torna_a_serie_indisponivel(
    base, registro, tmp_path, erros_logados
):
    nova, fixados = _versao_nova_item_d(base)
    MlflowClient().set_model_version_tag(
        nome_modelo('item D', 'diaria'), nova.versao, 'hash_artefato', 'f' * 64
    )

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        resposta = _pedir(c, 'item D', 'diaria')
        assert _pedir(c, 'item D', 'semanal').status_code == HTTP_OK

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert 'hash divergente' in resposta.json()['mensagem']
    assert any('hash divergente' in m for m in erros_logados)


def test_artefato_trocado_e_detectado_sem_ser_carregado(
    base, registro, tmp_path, erros_logados
):
    nova, fixados = _versao_nova_item_d(base)
    versao = MlflowClient().get_model_version(
        nome_modelo('item D', 'diaria'), nova.versao
    )
    artefato = Path(mlflow.artifacts.download_artifacts(versao.source))
    # Bytes que não são um pickle: carregar antes de conferir daria outro erro.
    (artefato / 'python_model.pkl').write_bytes(b'artefato trocado')

    with _app_com(base, tmp_path, modelos_fixados=fixados) as c:
        resposta = _pedir(c, 'item D', 'diaria')

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert 'hash divergente' in resposta.json()['mensagem']
    assert any('hash divergente' in m for m in erros_logados)


def test_consulta_ao_registro_nao_vira_falso_alarme(base, registro, tmp_path):
    """Baixar por nome reescreve `registered_model_meta` no armazenamento."""
    nome = nome_modelo('item D', 'semanal')
    versao = registro['item D', 'semanal'].versao
    mlflow.artifacts.download_artifacts(f'models:/{nome}/{versao}')

    with _app_com(base, tmp_path) as c:
        resposta = _pedir(c, 'item D', 'semanal')

    assert resposta.status_code == HTTP_OK


# --- origem fixa: data de referência e horizonte ------------------------


def _quantidades(resposta) -> list[float]:
    return [p['quantidade_prevista'] for p in resposta.json()['periodos']]


def _alvos(resposta) -> list[str]:
    return [p['data_alvo'] for p in resposta.json()['periodos']]


def test_horizonte_padrao_e_um_periodo(cliente):
    assert len(_pedir(cliente).json()['periodos']) == 1


def test_horizonte_maior_lista_um_item_por_periodo(cliente):
    resposta = _pedir(cliente, 'item B', 'diaria', horizonte=3)

    assert _quantidades(resposta) == pytest.approx([1, 2, 3])
    assert _alvos(resposta) == [
        str(FIM_DIARIA + timedelta(days=i)) for i in (1, 2, 3)
    ]


def test_referencia_depois_do_treino_fatia_os_passos_seguintes(cliente):
    referencia = FIM_DIARIA + timedelta(days=2)

    resposta = _pedir(
        cliente,
        'item B',
        'diaria',
        data_referencia=str(referencia),
        horizonte=2,
    )

    assert _quantidades(resposta) == pytest.approx([3, 4])
    assert _alvos(resposta) == [
        str(referencia + timedelta(days=i)) for i in (1, 2)
    ]


def test_ultimo_passo_validado_e_servido(cliente):
    referencia = FIM_DIARIA + timedelta(days=13)

    resposta = _pedir(
        cliente, 'item B', 'diaria', data_referencia=str(referencia)
    )

    assert resposta.status_code == HTTP_OK
    assert _quantidades(resposta) == pytest.approx([7])


@pytest.mark.parametrize('dia', range(7))
def test_semanal_normaliza_para_a_segunda(cliente, dia):
    referencia = SEGUNDA_FINAL + timedelta(days=dia)

    resposta = _pedir(
        cliente, granularidade='semanal', data_referencia=str(referencia)
    )

    assert resposta.status_code == HTTP_OK
    assert resposta.json()['data_referencia'] == str(SEGUNDA_FINAL)
    assert _alvos(resposta) == [str(SEGUNDA_FINAL + timedelta(days=7))]


def test_semanal_conta_passos_em_semanas(cliente):
    proxima = SEGUNDA_FINAL + timedelta(days=9)

    resposta = _pedir(
        cliente, granularidade='semanal', data_referencia=str(proxima)
    )

    assert resposta.status_code == HTTP_OK
    assert _alvos(resposta) == [str(SEGUNDA_FINAL + timedelta(days=14))]


def test_referencia_anterior_ao_treino_e_rejeitada(cliente):
    resposta = _pedir(
        cliente, data_referencia=str(FIM_DIARIA - timedelta(days=1))
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['codigo'] == 'data_referencia_invalida'
    assert 'data_referencia' in _detalhes(resposta)


def test_semana_anterior_a_do_treino_e_rejeitada(cliente):
    resposta = _pedir(
        cliente,
        granularidade='semanal',
        data_referencia=str(SEGUNDA_FINAL - timedelta(days=1)),
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['codigo'] == 'data_referencia_invalida'


@pytest.mark.parametrize(
    ('granularidade', 'horizonte', 'limite'),
    [('diaria', 15, '14 dias'), ('semanal', 3, '2 semanas')],
)
def test_horizonte_acima_do_limite_tem_justificativa(
    cliente, granularidade, horizonte, limite
):
    resposta = _pedir(
        cliente, granularidade=granularidade, horizonte=horizonte
    )

    assert resposta.status_code == HTTP_INVALIDO
    corpo = resposta.json()
    assert corpo['codigo'] == 'horizonte_acima_do_limite'
    assert limite in corpo['mensagem']
    assert 'validado empiricamente' in corpo['mensagem']
    assert 'horizonte' in _detalhes(resposta)


@pytest.mark.parametrize(
    ('granularidade', 'horizonte'), [('diaria', 14), ('semanal', 2)]
)
def test_horizonte_no_limite_e_aceito(cliente, granularidade, horizonte):
    resposta = _pedir(
        cliente, granularidade=granularidade, horizonte=horizonte
    )

    assert resposta.status_code == HTTP_OK
    assert len(resposta.json()['periodos']) == horizonte


def test_limite_vale_para_o_ultimo_passo_e_nao_so_para_o_horizonte(cliente):
    referencia = FIM_DIARIA + timedelta(days=10)

    resposta = _pedir(cliente, data_referencia=str(referencia), horizonte=5)

    assert resposta.status_code == HTTP_INVALIDO
    corpo = resposta.json()
    assert corpo['codigo'] == 'horizonte_acima_do_limite'
    assert 'passo 15' in corpo['mensagem']


def test_referencia_longe_demais_e_rejeitada(cliente):
    resposta = _pedir(
        cliente, data_referencia=str(FIM_DIARIA + timedelta(days=365))
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['codigo'] == 'horizonte_acima_do_limite'


# --- validação de entrada -----------------------------------------------


def test_sku_inexistente_responde_404(cliente):
    resposta = _pedir(cliente, sku='item Z')

    assert resposta.status_code == HTTP_NAO_ENCONTRADO
    assert resposta.json()['codigo'] == 'sku_inexistente'
    assert 'sku' in _detalhes(resposta)


def test_mensal_e_rejeitada_com_a_justificativa(cliente):
    resposta = cliente.post(
        '/predicoes',
        json={
            'sku': 'item A',
            'granularidade': 'mensal',
            'data_referencia': str(FIM_DIARIA),
        },
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['codigo'] == 'requisicao_invalida'
    assert 'ADR 0001' in _detalhes(resposta)['granularidade']


@pytest.mark.parametrize('granularidade', ['anual', 'DIARIA', '', 7, None])
def test_granularidade_nao_suportada_e_rejeitada(cliente, granularidade):
    resposta = cliente.post(
        '/predicoes',
        json={
            'sku': 'item A',
            'granularidade': granularidade,
            'data_referencia': str(FIM_DIARIA),
        },
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert 'não suportada' in _detalhes(resposta)['granularidade']


@pytest.mark.parametrize(
    'data', ['ontem', '2021-02-30', '19/08/2021', '20210819', 1629331200, None]
)
def test_data_invalida_e_rejeitada(cliente, data):
    resposta = _pedir(cliente, data_referencia=data)

    assert resposta.status_code == HTTP_INVALIDO
    assert 'AAAA-MM-DD' in _detalhes(resposta)['data_referencia']


@pytest.mark.parametrize('campo', ['sku', 'granularidade', 'data_referencia'])
def test_campo_ausente_e_rejeitado(cliente, campo):
    corpo = {
        'sku': 'item A',
        'granularidade': 'diaria',
        'data_referencia': str(FIM_DIARIA),
    }
    del corpo[campo]

    resposta = cliente.post('/predicoes', json=corpo)

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['codigo'] == 'requisicao_invalida'
    assert _detalhes(resposta)[campo] == 'campo obrigatório ausente'


@pytest.mark.parametrize('horizonte', [0, -1, 1.5, '2', True, None])
def test_horizonte_invalido_e_rejeitado(cliente, horizonte):
    resposta = _pedir(cliente, horizonte=horizonte)

    assert resposta.status_code == HTTP_INVALIDO
    assert 'horizonte' in _detalhes(resposta)


def test_campo_desconhecido_e_rejeitado(cliente):
    resposta = _pedir(cliente, horizontes=2)

    assert resposta.status_code == HTTP_INVALIDO
    assert 'horizontes' in _detalhes(resposta)


def test_corpo_que_nao_e_json_tem_erro_estruturado(cliente):
    resposta = cliente.post(
        '/predicoes',
        content='{',
        headers={'content-type': 'application/json'},
    )

    assert resposta.status_code == HTTP_INVALIDO
    assert resposta.json()['detalhes'][0]['campo'] == 'corpo'


# --- histórico ----------------------------------------------------------


def _ler_historico(caminho: Path) -> list[dict]:
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        cursor = con.execute('SELECT * FROM previsoes ORDER BY data_alvo')
        colunas = [c[0] for c in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        con.close()


def test_previsao_servida_e_gravada_por_periodo_alvo(base, registro, tmp_path):
    with _app_com(base, tmp_path) as c:
        corpo = _pedir(c, 'item B', 'diaria', horizonte=2).json()

    linhas = _ler_historico(tmp_path / 'h.duckdb')
    assert [linha['data_alvo'] for linha in linhas] == [
        FIM_DIARIA + timedelta(days=i) for i in (1, 2)
    ]
    assert {linha['id_requisicao'] for linha in linhas} == {
        corpo['id_requisicao']
    }
    primeira, periodo = linhas[0], corpo['periodos'][0]
    assert primeira['sku'] == 'item B'
    assert primeira['granularidade'] == 'diaria'
    assert primeira['data_referencia'] == FIM_DIARIA
    assert primeira['data_geracao'] is not None
    assert primeira['versao_modelo'] == corpo['versao_modelo']
    assert primeira['hash_artefato'] == corpo['hash_artefato']
    assert primeira['experimento_id'] == corpo['experimento_id']
    assert primeira['run_id'] == corpo['run_id']
    assert 'confianca' not in primeira
    assert primeira['valor_unitario'] == pytest.approx(15)
    for campo in (
        'quantidade_prevista',
        'valor_previsto',
        'limite_inferior_80',
        'limite_superior_80',
        'limite_inferior_95',
        'limite_superior_95',
    ):
        assert primeira[campo] == pytest.approx(periodo[campo])


def test_previsao_servida_aparece_na_consulta_da_api(base, registro, tmp_path):
    with _app_com(base, tmp_path) as c:
        prevista = _pedir(c, 'item B', 'diaria', horizonte=2).json()
        resposta = c.get(
            '/previsoes',
            params={'sku': 'B', 'granularidade': 'diaria'},
        )

    assert resposta.status_code == HTTP_OK
    corpo = resposta.json()
    assert corpo['total'] == len(prevista['periodos'])
    assert {item['id_requisicao'] for item in corpo['itens']} == {
        prevista['id_requisicao']
    }
    assert {item['data_alvo'] for item in corpo['itens']} == {
        periodo['data_alvo'] for periodo in prevista['periodos']
    }


def test_limites_indisponiveis_vao_nulos_ao_historico(
    base, registro, tmp_path
):
    with _app_com(base, tmp_path) as c:
        assert _pedir(c, 'item B', 'semanal').status_code == HTTP_OK

    linha = _ler_historico(tmp_path / 'h.duckdb')[0]
    assert linha['limite_inferior_95'] is None
    assert linha['limite_superior_95'] is None


REQUISICOES_SERVIDAS = 2


def test_erro_nao_grava_e_historico_persiste_entre_inicios(
    base, registro, tmp_path
):
    with _app_com(base, tmp_path) as c:
        assert _pedir(c).status_code == HTTP_OK
        assert _pedir(c, horizonte=15).status_code == HTTP_INVALIDO
        assert _pedir(c, sku='item Z').status_code == HTTP_NAO_ENCONTRADO
        assert _pedir(c, 'item C', 'diaria').status_code == HTTP_INDISPONIVEL
    with _app_com(base, tmp_path) as c:
        assert _pedir(c).status_code == HTTP_OK

    assert len(_ler_historico(tmp_path / 'h.duckdb')) == REQUISICOES_SERVIDAS


def test_previsao_nao_e_servida_sem_registro(
    base, registro, tmp_path, monkeypatch
):
    def falhar(self, linhas):
        raise HistoricoIndisponivel('sem histórico')

    monkeypatch.setattr(Historico, 'registrar', falhar)

    with _app_com(base, tmp_path) as c:
        resposta = _pedir(c)

    assert resposta.status_code == HTTP_INDISPONIVEL
    assert resposta.json()['codigo'] == 'historico_indisponivel'


# --- nenhum treino ------------------------------------------------------


def _bloquear(*_args, **_kwargs):
    raise AssertionError('requisição disparou treino')


def _contagem() -> tuple[int, int]:
    cliente = MlflowClient()
    experimentos = [e.experiment_id for e in cliente.search_experiments()]
    return (
        len(cliente.search_runs(experimentos, max_results=1000)),
        len(cliente.search_model_versions(max_results=1000)),
    )


def test_nenhuma_requisicao_dispara_treino(
    base, registro, tmp_path, monkeypatch
):
    with _app_com(base, tmp_path) as c:
        antes = _contagem()
        monkeypatch.setattr(treino, 'treinar_serie', _bloquear)
        monkeypatch.setattr(treino, '_treinar_candidato', _bloquear)
        monkeypatch.setattr(algoritmos, 'criar', _bloquear)
        monkeypatch.setattr(intervalos, 'calibrar', _bloquear)
        for classe in algoritmos.ALGORITMOS.values():
            if hasattr(classe, 'ajustar'):
                monkeypatch.setattr(classe, 'ajustar', _bloquear)

        assert _pedir(c, horizonte=14).status_code == HTTP_OK
        assert _pedir(c, 'item A', 'semanal').status_code == HTTP_OK
        assert _pedir(c, 'item C', 'diaria').status_code == HTTP_INDISPONIVEL

        assert _contagem() == antes


def test_carregar_modelos_nao_altera_o_registro(base, registro, tmp_path):
    antes = _contagem()

    with _app_com(base, tmp_path):
        pass

    assert _contagem() == antes


# --- catálogo, Swagger e CLI --------------------------------------------


def test_carrega_um_modelo_por_serie(cliente):
    catalogo = cliente.app.state.modelos

    assert set(catalogo.modelos) | set(catalogo.indisponiveis) == {
        (sku, granularidade)
        for sku in SKUS
        for granularidade in GRANULARIDADES
    }
    assert not set(catalogo.modelos) & set(catalogo.indisponiveis)


def test_swagger_documenta_a_rota(cliente):
    esquema = cliente.get('/openapi.json').json()
    rota = esquema['paths']['/predicoes']['post']
    componentes = esquema['components']['schemas']

    assert rota['summary']
    assert rota['description']
    assert {'200', '404', '422', '503'} <= set(rota['responses'])
    for status in ('404', '422', '503'):
        resposta = rota['responses'][status]
        conteudo = resposta['content']['application/json']
        assert resposta['description']
        assert conteudo['example']['codigo']
        assert conteudo['schema']['$ref'].endswith('/ErroResposta')
    assert componentes['PedidoPredicao']['examples']
    assert componentes['RespostaPredicao']['examples']
    for esquema_modelo in ('PedidoPredicao', 'RespostaPredicao'):
        for campo in componentes[esquema_modelo]['properties'].values():
            assert campo['description']
    assert cliente.get('/docs').status_code == HTTP_OK


def test_servir_usa_um_unico_worker(monkeypatch, base, registro):
    chamadas = []
    monkeypatch.setattr(
        modulo_cli.uvicorn,
        'run',
        lambda app, **kwargs: chamadas.append(kwargs),
    )
    monkeypatch.setattr(modulo_cli, 'Settings', lambda: base)
    monkeypatch.setattr(modulo_cli, 'configurar_logs', lambda nivel: None)

    assert modulo_cli.servir(porta=8123) == 0

    assert chamadas == [{'host': base.api_host, 'port': 8123, 'workers': 1}]
