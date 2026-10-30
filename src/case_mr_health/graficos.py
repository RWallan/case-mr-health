"""Gráfico por série do modelo selecionado (#12).

Mostra treino, folds de teste, previsão e intervalos. O OOT aparece só como
período reservado, com a previsão: seus valores nunca são abertos aqui, pois
a série vem de `carregar_serie`, que lê a visão de desenvolvimento.
"""

import matplotlib as mpl

mpl.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import mlflow  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow import MlflowClient  # noqa: E402
from mlflow.artifacts import load_dict  # noqa: E402

from case_mr_health.config import Settings  # noqa: E402
from case_mr_health.treino import (  # noqa: E402
    ARTEFATO_BACKTEST,
    CAMINHO_MODELO,
    _particao,
    carregar_serie,
    horizonte_maximo,
)

ARTEFATO_GRAFICO = 'grafico_serie.png'
COR_OBSERVADO = '#52514e'
COR_PREVISAO = '#2a78d6'
COR_RESERVADO = '#e4e3dd'
COR_FUNDO = '#fcfcfb'
LARGURA = 11
ALTURA = 4.5


def _banda(eixo, x, dados, previsto, rotulos=(None, None)) -> None:
    for nivel, alfa, rotulo in zip(('95', '80'), (0.15, 0.3), rotulos):
        inferior = dados.get(f'inferior_{nivel}')
        superior = dados.get(f'superior_{nivel}')
        if inferior is None or None in inferior:
            continue
        eixo.fill_between(
            x,
            inferior,
            superior,
            color=COR_PREVISAO,
            alpha=alfa,
            linewidth=0,
            label=rotulo,
        )
    eixo.plot(x, previsto, color=COR_PREVISAO, linewidth=2, marker='o', ms=3)


def desenhar(serie: pd.Series, particao, folds: list[dict], futuro, titulo):
    """Figura da série; `futuro` é o `DataFrame` da previsão pós-treino."""
    figura, eixo = plt.subplots(figsize=(LARGURA, ALTURA), facecolor=COR_FUNDO)
    eixo.set_facecolor(COR_FUNDO)
    eixo.plot(
        serie.index,
        serie.to_numpy(),
        color=COR_OBSERVADO,
        linewidth=1.2,
        label='Venda observada (desenvolvimento)',
    )
    rotulos = ('Intervalo de 95%', 'Intervalo de 80%')
    for fold in folds:
        x = pd.date_range(
            fold['teste_inicio'],
            periods=len(fold['previsto']),
            freq=_freq(particao),
        )
        _banda(eixo, x, fold, fold['previsto'], rotulos)
        rotulos = (None, None)
    inicio = pd.Timestamp(particao.oot_inicio)
    fim = pd.Timestamp(particao.oot_fim)
    eixo.axvspan(
        inicio,
        fim,
        color=COR_RESERVADO,
        zorder=0,
        label='Período OOT reservado (valores não abertos)',
    )
    x = pd.date_range(inicio, periods=len(futuro), freq=_freq(particao))
    _banda(eixo, x, futuro.to_dict('list'), futuro['previsao'])
    eixo.plot([], [], color=COR_PREVISAO, linewidth=2, label='Previsão')
    eixo.set_title(titulo, loc='left', fontsize=12)
    eixo.set_xlabel('Data')
    eixo.set_ylabel('Quantidade vendida')
    eixo.set_ylim(bottom=0)
    eixo.grid(axis='y', color=COR_RESERVADO, linewidth=0.6)
    eixo.spines[['top', 'right']].set_visible(False)
    eixo.legend(frameon=False, ncols=2, fontsize=9, loc='upper left')
    figura.tight_layout()
    return figura


def _freq(particao) -> str:
    return 'D' if particao.granularidade == 'diaria' else 'W-MON'


def registrar(cfg: Settings, sku: str, granularidade: str, selecao) -> None:
    """Desenha a série do vencedor e grava no run dele."""
    run_id = selecao.vencedor.run_id
    particao = _particao(cfg, sku, granularidade)
    backtest = load_dict(f'runs:/{run_id}/{ARTEFATO_BACKTEST}')
    modelo = mlflow.pyfunc.load_model(f'runs:/{run_id}/{CAMINHO_MODELO}')
    futuro = modelo.unwrap_python_model().prever_com_intervalos(
        horizonte_maximo(cfg, granularidade)
    )
    figura = desenhar(
        carregar_serie(cfg, sku, granularidade),
        particao,
        backtest['folds'],
        futuro,
        f'{sku} {granularidade}: {selecao.vencedor.algoritmo}',
    )
    MlflowClient().log_figure(run_id, figura, ARTEFATO_GRAFICO)
    plt.close(figura)
