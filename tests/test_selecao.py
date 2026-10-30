import json

import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow import MlflowClient
from mlflow.artifacts import load_dict

from case_mr_health.candidatos import SKUS
from case_mr_health.cli import app
from case_mr_health.config import Settings
from case_mr_health.graficos import ARTEFATO_GRAFICO, desenhar
from case_mr_health.intervalos import INDISPONIVEL
from case_mr_health.particoes import GRANULARIDADES, carregar_particoes
from case_mr_health.selecao import (
    ALIAS_SELECIONADO,
    E_O_BASELINE,
    INDISTINGUIVEL,
    PIOR,
    SUPERA,
    Avaliado,
    avaliar_utilidade_confianca,
    carregar_rodada,
    ganho_pareado,
    publicar_selecao,
    resumo_markdown,
    selecionar,
    sem_pos_hoc,
)
from case_mr_health.treino import (
    ARTEFATO_BACKTEST,
    nome_modelo,
    treinar_serie,
    treinar_todas,
)
from tests.test_treino import PADROES, _gravar_origem

SERIE = ('item B', 'semanal')
SEED = 5
RUNS_SEMANAIS = 3
SERIES_TOTAIS = 8


def _run(algoritmo, maes, papel='candidato', **extra):
    medias = {'mase': 1.0, 'rmse': float(np.mean(maes)), **extra.pop('m', {})}
    return Avaliado(
        run_id=f'{algoritmo}-{maes}',
        algoritmo=algoritmo,
        papel=papel,
        hiperparametros=extra.pop('hp', {}),
        mae_folds=tuple(float(m) for m in maes),
        medias=medias,
        **extra,
    )


BASE = _run('naive', [4, 4, 4, 4], 'baseline')
MEDIA = _run('media_historica', [3, 3, 5, 5], 'baseline')


def test_baseline_de_referencia_e_o_de_menor_mae():
    melhor = _run('media_historica', [3, 3, 3, 3], 'baseline')

    assert selecionar('item A', 'semanal', [BASE, melhor]).baseline == melhor


def test_candidato_com_ganho_acima_de_um_erro_padrao_vence():
    candidato = _run('ets_ses', [2, 2.1, 1.9, 2])

    selecao = selecionar('item A', 'semanal', [BASE, candidato])

    assert selecao.vencedor == candidato
    assert selecao.comparacoes[0].supera


def test_ganho_confere_com_o_calculo_a_mao():
    # d = 1, -1, 2, 2: média 1 e ep = sqrt(2)/2 = 0,7071.
    candidato = _run('ets_ses', [3, 5, 2, 2])

    selecao = selecionar('item A', 'semanal', [BASE, candidato])

    assert selecao.comparacoes[0].media == pytest.approx(1.0)
    assert selecao.comparacoes[0].erro_padrao == pytest.approx(
        0.7071, abs=1e-4
    )
    assert selecao.vencedor == candidato


def test_ganho_abaixo_de_um_erro_padrao_mantem_o_baseline():
    # Menor MAE médio que o baseline, mas com ganho instável entre folds.
    candidato = _run('ets_ses', [0, 8, 0, 7])

    selecao = selecionar('item A', 'semanal', [BASE, candidato])

    assert candidato.mae < BASE.mae
    assert selecao.vencedor == BASE


def test_entre_os_que_superam_vence_o_de_menor_mae():
    bom = _run('ets_ses', [3, 3, 3, 3.1])
    melhor = _run('tsb', [2, 2, 2, 2.1])

    selecao = selecionar('item A', 'diaria', [BASE, bom, melhor])

    assert selecao.vencedor == melhor


def test_candidato_que_nao_supera_nao_vence_mesmo_com_menor_mae():
    estavel = _run('ets_ses', [3, 3, 3, 3.1])
    instavel = _run('tsb', [0, 8, 0, 3.5])

    selecao = selecionar('item A', 'diaria', [BASE, estavel, instavel])

    assert instavel.mae < estavel.mae
    assert selecao.vencedor == estavel


def test_empate_fica_com_o_mais_simples():
    simples = _run('sba', [2, 2, 2, 2.1], hp={'alfa': 0.1})
    complexo = _run('sarima', [2, 2, 2, 2.1])

    selecao = selecionar('item A', 'diaria', [BASE, complexo, simples])

    assert selecao.vencedor == simples


def test_sem_intervalo_nao_pode_ser_selecionado():
    candidato = _run('ets_ses', [1, 1, 1, 1.1], intervalo_metodo=INDISPONIVEL)

    selecao = selecionar('item A', 'semanal', [BASE, candidato])

    assert selecao.vencedor == BASE
    assert selecao.excluidos == ('ets_ses',)


def test_serie_sem_baseline_elegivel_falha():
    with pytest.raises(ValueError, match='sem baseline'):
        selecionar('item A', 'semanal', [_run('ets_ses', [1, 1, 1, 1])])


def test_sinaliza_rmse_e_vies_sem_mudar_o_vencedor():
    vencedor = _run(
        'ets_ses',
        [2, 2.1, 1.9, 2],
        m={'rmse': 9.0, 'vies_relativo': -0.3},
    )

    selecao = selecionar('item A', 'semanal', [BASE, vencedor])

    assert selecao.vencedor == vencedor
    assert any('menor RMSE: naive' in s for s in selecao.sinais)
    assert any('viés relativo' in s for s in selecao.sinais)


def test_sinaliza_mudanca_na_sensibilidade_do_item_c():
    chave = 'sens_sem_periodo_atipico_mae'
    vencedor = _run('ets_ses', [2, 2.1, 1.9, 2], m={chave: 3.0})
    baseline = _run('naive', [4, 4, 4, 4], 'baseline', m={chave: 1.0})

    selecao = selecionar('item C', 'semanal', [baseline, vencedor])

    assert selecao.vencedor == vencedor
    assert any('sem_periodo_atipico: naive' in s for s in selecao.sinais)


@pytest.mark.parametrize(
    ('maes', 'esperado'),
    [
        ([2, 2.1, 1.9, 2], SUPERA),
        ([6, 6.1, 5.9, 6], PIOR),
        ([0, 8, 0, 8], INDISTINGUIVEL),
    ],
)
def test_ganho_pareado_classifica(maes, esperado):
    assert ganho_pareado(BASE, _run('ets_ses', maes))[3] == esperado


def test_ganho_pareado_e_relativo_ao_mae_do_baseline():
    ganho, *_ = ganho_pareado(BASE, _run('ets_ses', [3, 3, 3, 3]))

    assert ganho == pytest.approx(0.25)


@pytest.mark.parametrize(
    ('diaria', 'semanal', 'inuteis'),
    [
        (['Boa', 'Média', 'Boa', 'Ruim'], ['Boa'] * 4, []),
        (
            ['Boa', 'Média', 'Insuficiente', 'Insuficiente'],
            ['Insuficiente', 'Insuficiente', 'Insuficiente', 'Boa'],
            ['I1'],
        ),
        (['Boa'] * 4, ['Boa'] * 4, ['I2']),
        (['Boa', 'Média', 'Ruim', 'Boa'], ['Insuficiente'] * 4, ['I3']),
    ],
)
def test_condicoes_de_inutilidade(diaria, semanal, inuteis):
    resultado = avaliar_utilidade_confianca({
        'diaria': diaria,
        'semanal': semanal,
    })

    assert [k for k in ('I1', 'I2', 'I3') if resultado[k]] == inuteis
    assert resultado['inutil'] is bool(inuteis)


def test_resumo_traz_o_baseline_vencedor_como_resultado():
    selecao = selecionar('item A', 'semanal', [BASE, MEDIA])

    texto = resumo_markdown('r1', [selecao])

    assert E_O_BASELINE in texto
    assert 'item A semanal' in texto


def test_naive_sai_so_das_series_diarias():
    assert sem_pos_hoc('diaria', [BASE, MEDIA]) == [MEDIA]
    assert sem_pos_hoc('semanal', [BASE, MEDIA]) == [BASE, MEDIA]


def test_grafico_so_recebe_o_desenvolvimento():
    indice = pd.date_range('2021-06-07', periods=20, freq='D')
    particao = type(
        'P',
        (),
        {
            'granularidade': 'diaria',
            'oot_inicio': indice[-1] + pd.Timedelta(days=1),
            'oot_fim': indice[-1] + pd.Timedelta(days=14),
        },
    )()
    fold = {
        'teste_inicio': '2021-06-20',
        'previsto': [1.0] * 7,
        'inferior_80': [0.5] * 7,
        'superior_80': [1.5] * 7,
        'inferior_95': [0.1] * 7,
        'superior_95': [1.9] * 7,
    }
    futuro = pd.DataFrame({
        'previsao': [2.0] * 14,
        'inferior_80': [1.0] * 14,
        'superior_80': [3.0] * 14,
        'inferior_95': [0.5] * 14,
        'superior_95': [3.5] * 14,
    })

    figura = desenhar(
        pd.Series(np.arange(20.0), index=indice), particao, [fold], futuro, 't'
    )

    observado = figura.axes[0].lines[0]
    assert len(observado.get_ydata()) == len(indice)


def test_grafico_mostra_o_intervalo_de_fold_com_um_ponto():
    indice = pd.date_range('2021-06-07', periods=8, freq='W-MON')
    particao = type(
        'P',
        (),
        {
            'granularidade': 'semanal',
            'oot_inicio': indice[-1] + pd.Timedelta(days=7),
            'oot_fim': indice[-1] + pd.Timedelta(days=20),
        },
    )()
    fold = {
        'teste_inicio': indice[-1].isoformat(),
        'previsto': [10.0],
        'inferior_80': [8.0],
        'superior_80': [12.0],
        'inferior_95': [6.0],
        'superior_95': [14.0],
    }
    futuro = pd.DataFrame({'previsao': [10.0, 10.0]})

    figura = desenhar(
        pd.Series(np.arange(8.0), index=indice), particao, [fold], futuro, 't'
    )

    rotulos = figura.axes[0].get_legend_handles_labels()[1]
    assert 'Intervalo de 80%' in rotulos


@pytest.fixture
def cfg(tmp_path) -> Settings:
    cfg = Settings(
        db_path=tmp_path / 'origem.duckdb',
        desenvolvimento_db_path=tmp_path / 'dev.duckdb',
        oot_db_path=tmp_path / 'fora.duckdb',
        mlflow_tracking_uri=f'sqlite:///{tmp_path / "mlflow.db"}',
        mlflow_artifact_dir=tmp_path / 'artefatos',
        intervalo_max_origens=5,
    )
    _gravar_origem(cfg, PADROES)
    return cfg


def test_todas_as_series_sao_o_padrao_de_treinar_todas(monkeypatch, cfg):
    chamadas = []
    monkeypatch.setattr(
        'case_mr_health.treino.treinar_serie',
        lambda _cfg, sku, gran, seed, rodada: chamadas.append((
            sku,
            gran,
            seed,
            rodada,
        )),
    )

    rodada, _ = treinar_todas(cfg, SEED)

    assert len(chamadas) == SERIES_TOTAIS
    assert {(s, g) for s, g, *_ in chamadas} == {
        (s, g) for s in SKUS for g in GRANULARIDADES
    }
    assert {r for *_, r in chamadas} == {rodada}


@pytest.mark.parametrize(
    'args',
    [
        ['treinar'],
        ['treinar', '--sku', 'A'],
        ['treinar', '--todas', '--sku', 'A', '--granularidade', 'diaria'],
    ],
)
def test_cli_exige_todas_ou_uma_serie(args):
    assert app(args, result_action='return_value') == 1


@pytest.mark.lento
def test_rodada_ignora_runs_de_outra_execucao(cfg):
    treinar_serie(cfg, *SERIE, SEED)
    rodada, _ = treinar_todas(cfg, SEED, (SERIE,))

    series = carregar_rodada(cfg, rodada)

    assert len(series[SERIE]) == RUNS_SEMANAIS


@pytest.mark.lento
def test_publicacao_marca_grava_grafico_e_nao_cria_champion(cfg, tmp_path):
    rodada, _ = treinar_todas(cfg, SEED, (SERIE,))
    resumo = tmp_path / 'resumo.md'

    [selecao] = publicar_selecao(cfg, rodada, resumo)

    nome = nome_modelo(*SERIE)
    cliente = MlflowClient()
    versao = cliente.get_model_version_by_alias(nome, ALIAS_SELECIONADO)
    assert versao.run_id == selecao.vencedor.run_id
    with pytest.raises(mlflow.MlflowException):
        cliente.get_model_version_by_alias(nome, 'champion')
    artefatos = {
        a.path for a in cliente.list_artifacts(selecao.vencedor.run_id)
    }
    assert {ARTEFATO_GRAFICO, 'selecao.json', ARTEFATO_BACKTEST} <= artefatos
    assert resumo.read_text(encoding='utf-8').startswith('# Resumo')


@pytest.mark.lento
def test_backtest_gravado_para_de_antes_do_oot(cfg):
    rodada, [resumo] = treinar_todas(cfg, SEED, (SERIE,))

    backtest = load_dict(f'runs:/{resumo.runs[0].run_id}/{ARTEFATO_BACKTEST}')

    particao = next(
        p for p in carregar_particoes(cfg) if (p.sku, p.granularidade) == SERIE
    )
    assert json.dumps(backtest)
    assert all(
        f['teste_fim'] < particao.oot_inicio.isoformat()
        for f in backtest['folds']
    )
    assert rodada == resumo.rodada
