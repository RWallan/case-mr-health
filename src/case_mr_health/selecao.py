"""Seleção do modelo de cada série, só no backtest (#12).

O critério foi fixado antes de qualquer resultado de candidato, em
`docs/relatorio/fase2/12-pre-registro.md`. Um candidato só substitui o melhor
baseline se o ganho pareado nos folds passar de um erro-padrão: com 4 a 5
folds isso é um freio contra a escolha por acaso, não prova de superioridade.
A publicação aqui é o alias `selecionado`; o `champion` é do #13.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import mlflow
import numpy as np
from loguru import logger
from mlflow import MlflowClient
from scipy import stats

from case_mr_health import confianca, graficos
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.intervalos import INDISPONIVEL
from case_mr_health.particoes import GRANULARIDADES
from case_mr_health.treino import nome_experimento, nome_modelo

ALIAS_SELECIONADO = 'selecionado'
BASELINE = 'baseline'
ORDEM_SIMPLICIDADE = (
    'naive',
    'media_historica',
    'naive_sazonal',
    'ets_ses',
    'sba',
    'croston',
    'tsb',
    'ets_holt_winters_aditivo',
    'sarima',
)
# Desvio do pré-registro, aprovado pelo usuário depois de ver os resultados
# e antes do OOT (`fase2/12.md`): em série diária intermitente, o naive repete
# o último dia por todo o horizonte. No item B, isso daria zero por 14 dias.
FORA_POS_HOC = (('diaria', 'naive'),)
TOLERANCIA_EMPATE = 1e-9
LIMITE_VIES_RELATIVO = 0.20
NIVEL_IC_GANHO = 0.80
MIN_SELECIONADOS_CLASSIFICADOS = 4
MIN_FAIXAS = 2
SUPERA = 'Supera'
PIOR = 'Pior'
INDISTINGUIVEL = 'Indistinguível'
E_O_BASELINE = 'É o baseline'


@dataclass(frozen=True)
class Avaliado:
    """Um run elegível, com o que a regra e o resumo precisam."""

    run_id: str
    algoritmo: str
    papel: str
    hiperparametros: dict
    mae_folds: tuple[float, ...]
    medias: dict[str, float]
    intervalo_metodo: str = ''
    confianca: str = ''
    premissas_nao_atendidas: str = ''

    @property
    def mae(self) -> float:
        return float(np.mean(self.mae_folds))


@dataclass(frozen=True)
class Comparacao:
    """Diferença pareada `MAE_baseline - MAE_candidato` nos mesmos folds."""

    algoritmo: str
    hiperparametros: dict
    media: float
    erro_padrao: float
    supera: bool


@dataclass(frozen=True)
class Selecao:
    sku: str
    granularidade: str
    vencedor: Avaliado
    baseline: Avaliado
    comparacoes: tuple[Comparacao, ...]
    excluidos: tuple[str, ...] = ()
    sinais: tuple[str, ...] = ()


def diferenca_pareada(
    baseline: Avaliado, candidato: Avaliado
) -> tuple[float, float]:
    """Média e erro-padrão de `MAE_baseline - MAE_candidato` por fold."""
    d = np.subtract(baseline.mae_folds, candidato.mae_folds)
    return float(d.mean()), float(d.std(ddof=1) / np.sqrt(len(d)))


def ganho_pareado(
    baseline: Avaliado, modelo: Avaliado, nivel: float = NIVEL_IC_GANHO
) -> tuple[float, float, float, str]:
    """Ganho relativo ao baseline, IC t e status (alternativa à confiança)."""
    media, ep = diferenca_pareada(baseline, modelo)
    referencia = baseline.mae
    meia = stats.t.ppf((1 + nivel) / 2, len(baseline.mae_folds) - 1) * ep
    inferior = (media - meia) / referencia
    superior = (media + meia) / referencia
    status = INDISTINGUIVEL
    if inferior > 0:
        status = SUPERA
    elif superior < 0:
        status = PIOR
    return media / referencia, inferior, superior, status


def _simplicidade(run: Avaliado) -> tuple:
    return (
        ORDEM_SIMPLICIDADE.index(run.algoritmo),
        sorted(run.hiperparametros.items()),
    )


def _melhor(runs: list[Avaliado]) -> Avaliado:
    """Menor MAE; empates vão para o mais simples."""
    menor = min(r.mae for r in runs)
    empatados = [r for r in runs if r.mae - menor <= TOLERANCIA_EMPATE]
    return min(empatados, key=_simplicidade)


def elegiveis(runs: list[Avaliado]) -> tuple[list[Avaliado], tuple[str, ...]]:
    """Separa quem não pode ser servido por falta de intervalo."""
    aceitos = [r for r in runs if r.intervalo_metodo != INDISPONIVEL]
    fora = tuple(
        r.algoritmo for r in runs if r.intervalo_metodo == INDISPONIVEL
    )
    return aceitos, fora


def sem_pos_hoc(granularidade: str, runs: list[Avaliado]) -> list[Avaliado]:
    return [
        r for r in runs if (granularidade, r.algoritmo) not in FORA_POS_HOC
    ]


def selecionar(sku: str, granularidade: str, runs: list[Avaliado]) -> Selecao:
    """Aplica a regra do pré-registro a uma série."""
    aceitos, excluidos = elegiveis(runs)
    baselines = [r for r in aceitos if r.papel == BASELINE]
    if not baselines:
        raise ValueError(f'{sku}/{granularidade} sem baseline elegível')
    referencia = _melhor(baselines)
    comparacoes, superam = [], []
    for run in aceitos:
        if run.papel == BASELINE:
            continue
        media, ep = diferenca_pareada(referencia, run)
        supera = media > 0 and media > ep
        comparacoes.append(
            Comparacao(run.algoritmo, run.hiperparametros, media, ep, supera)
        )
        if supera:
            superam.append(run)
    vencedor = _melhor(superam) if superam else referencia
    return Selecao(
        sku,
        granularidade,
        vencedor,
        referencia,
        tuple(comparacoes),
        excluidos,
        _sinais(vencedor, aceitos),
    )


def _sinais(vencedor: Avaliado, aceitos: list[Avaliado]) -> tuple[str, ...]:
    """Avisos do pré-registro; nenhum deles muda o vencedor."""
    sinais = []
    pelo_rmse = min(aceitos, key=lambda r: r.medias['rmse'])
    if pelo_rmse.run_id != vencedor.run_id:
        sinais.append(f'menor RMSE: {pelo_rmse.algoritmo}')
    vies = vencedor.medias.get('vies_relativo', float('nan'))
    if abs(vies) > LIMITE_VIES_RELATIVO:
        sinais.append(f'viés relativo {vies:+.1%}')
    for variante in ('sem_periodo_atipico', 'sem_folds_1_2'):
        chave = f'sens_{variante}_mae'
        if chave not in vencedor.medias:
            continue
        outro = min(
            (r for r in aceitos if chave in r.medias),
            key=lambda r: r.medias[chave],
        )
        if outro.run_id != vencedor.run_id:
            sinais.append(f'menor MAE {variante}: {outro.algoritmo}')
    return tuple(sinais)


def avaliar_utilidade_confianca(status: dict[str, list[str]]) -> dict:
    """Condições I1 a I3 do pré-registro; `status` por granularidade."""
    todos = [s for lista in status.values() for s in lista]
    fora = [s for s in todos if s != confianca.INSUFICIENTE]
    condicoes = {
        'I1': len(fora) < MIN_SELECIONADOS_CLASSIFICADOS,
        'I2': len(set(fora)) < MIN_FAIXAS,
        'I3': all(s == confianca.INSUFICIENTE for s in status['semanal']),
    }
    return {
        **condicoes,
        'fora_de_insuficiente': len(fora),
        'inutil': any(condicoes.values()),
    }


def carregar_rodada(
    cfg: Settings, rodada: str
) -> dict[tuple[str, str], list[Avaliado]]:
    """Runs `FINISHED` da rodada, por série. Falhas ficam de fora (D-016)."""
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    cliente = MlflowClient()
    ids = [
        e.experiment_id
        for g in GRANULARIDADES
        if (e := cliente.get_experiment_by_name(nome_experimento(g)))
    ]
    runs = cliente.search_runs(
        ids,
        f"tags.rodada = '{rodada}' AND attributes.status = 'FINISHED'",
        max_results=1000,
    )
    series: dict[tuple[str, str], list[Avaliado]] = {}
    for run in runs:
        tags = run.data.tags
        chave = (tags['sku'], tags['granularidade'])
        series.setdefault(chave, []).append(_avaliado(cliente, run))
    return series


def _avaliado(cliente: MlflowClient, run) -> Avaliado:
    tags, params = run.data.tags, run.data.params
    historico = cliente.get_metric_history(run.info.run_id, 'mae_fold')
    return Avaliado(
        run.info.run_id,
        tags['algoritmo'],
        tags['papel'],
        {
            k.removeprefix('hp.'): v
            for k, v in params.items()
            if k.startswith('hp.')
        },
        tuple(m.value for m in sorted(historico, key=lambda m: m.step)),
        dict(run.data.metrics),
        tags.get('intervalo_metodo', ''),
        tags.get('confianca', ''),
        tags.get('premissas_nao_atendidas', ''),
    )


def publicar_selecao(
    cfg: Settings, rodada: str, resumo_path: Path
) -> list[Selecao]:
    """Seleciona, marca a versão, grava os gráficos e o resumo."""
    series = carregar_rodada(cfg, rodada)
    if not series:
        raise ValueError(f'Rodada sem runs: {rodada}')
    selecoes = [
        selecionar(sku, gran, sem_pos_hoc(gran, series[sku, gran]))
        for sku in SKUS
        for gran in GRANULARIDADES
        if (sku, gran) in series
    ]
    for selecao in selecoes:
        _marcar(selecao)
        graficos.registrar(cfg, selecao.sku, selecao.granularidade, selecao)
    resumo_path.parent.mkdir(parents=True, exist_ok=True)
    resumo_path.write_text(resumo_markdown(rodada, selecoes), encoding='utf-8')
    logger.info('Resumo em {}', resumo_path)
    return selecoes


def _marcar(selecao: Selecao) -> None:
    cliente = MlflowClient()
    nome = nome_modelo(selecao.sku, selecao.granularidade)
    run_id = selecao.vencedor.run_id
    [versao] = cliente.search_model_versions(f"run_id = '{run_id}'")
    cliente.set_registered_model_alias(nome, ALIAS_SELECIONADO, versao.version)
    cliente.set_tag(run_id, 'selecionado', 'true')
    cliente.log_dict(
        run_id,
        {
            'baseline_referencia': selecao.baseline.algoritmo,
            'sinais': list(selecao.sinais),
            'excluidos': list(selecao.excluidos),
            'comparacoes': [_comparacao(c) for c in selecao.comparacoes],
        },
        'selecao.json',
    )


def _comparacao(c: Comparacao) -> dict:
    return {
        'algoritmo': c.algoritmo,
        'hiperparametros': json.dumps(c.hiperparametros),
        'media': c.media,
        'erro_padrao': c.erro_padrao,
        'supera': c.supera,
    }


def _linha(s: Selecao) -> str:
    v, b = s.vencedor, s.baseline
    media, ep = diferenca_pareada(b, v)
    ganho = E_O_BASELINE if v.run_id == b.run_id else ganho_pareado(b, v)[3]
    cobertura = ' / '.join(
        f'{v.medias.get(f"cobertura_{n}", float("nan")):.2f}'
        for n in ('80', '95')
    )
    return (
        f'| {s.sku} {s.granularidade} | {v.algoritmo} {v.hiperparametros} | '
        f'{b.algoritmo} | {v.mae:.3f} | {b.mae:.3f} | {media:+.3f} | '
        f'{ep:.3f} | {v.medias["mase"]:.3f} | {cobertura} | '
        f'{v.confianca} | {ganho} | {"; ".join(s.sinais) or "-"} |'
    )


def resumo_markdown(rodada: str, selecoes: list[Selecao]) -> str:
    """Resumo por série; números só do backtest, sem o OOT."""
    status = {g: [] for g in GRANULARIDADES}
    for s in selecoes:
        status[s.granularidade].append(s.vencedor.confianca)
    linhas = [
        '# Resumo da seleção por série (#12)',
        '',
        f'Rodada `{rodada}`. Critério: `12-pre-registro.md`. Só backtest.',
        '',
        '| Série | Vencedor | Baseline | MAE | MAE baseline | d̄ | ep | '
        'MASE | Cobertura 80/95 | Confiança | Ganho pareado | Sinais |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- '
        '| --- |',
        *[_linha(s) for s in selecoes],
        '',
    ]
    if status['semanal'] and status['diaria']:
        linhas.append(
            f'Utilidade da confiança: {avaliar_utilidade_confianca(status)}'
        )
    return '\n'.join(linhas) + '\n'
