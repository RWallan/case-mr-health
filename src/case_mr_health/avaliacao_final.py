"""Avaliação final única no OOT, sem nova seleção (#13, ADR 0002).

Segue `docs/analysis/protocolo-avaliacao-final.md`. Tudo o que pode falhar
(portões da política de dados, aliases, hash dos artefatos, partições) é
conferido antes de o OOT ser aberto. A tentativa é marcada de forma
exclusiva e persistente imediatamente antes da abertura; se a marca existir,
nada é lido. Falha depois da marca não autoriza repetição.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from loguru import logger
from mlflow import MlflowClient
from mlflow.entities.model_registry import ModelVersion

from case_mr_health import graficos, metricas
from case_mr_health.api import mlflow_cliente
from case_mr_health.api.mlflow_cliente import ModeloRecusado
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.particoes import (
    DIAS_POR_PERIODO,
    GRANULARIDADES,
    Particao,
    carregar_particoes,
)
from case_mr_health.selecao import ALIAS_SELECIONADO
from case_mr_health.treino import (
    carregar_serie,
    horizonte_maximo,
    nome_modelo,
)

PROTOCOLO = Path('docs/analysis/protocolo-avaliacao-final.md')
RELATORIO = Path('docs/relatorio/fase4/13-avaliacao-final.md')
DECISOES_EXIGIDAS = ('D-019', 'D-020')
ARTEFATO_OOT = 'oot.json'
ARTEFATO_GRAFICO_OOT = 'grafico_oot.png'
NIVEIS = (80, 95)
_TABELAS_OOT = {
    'diaria': ('serie_diaria', 'data'),
    'semanal': ('serie_semanal', 'semana'),
}


@dataclass(frozen=True)
class Selecionado:
    """Versão `selecionado` já conferida, pronta para prever."""

    sku: str
    granularidade: str
    versao: ModelVersion
    algoritmo: str
    run_id: str
    modelo: object
    particao: Particao
    desenvolvimento: pd.Series


@dataclass(frozen=True)
class ResultadoOot:
    sku: str
    granularidade: str
    versao: str
    algoritmo: str
    run_id: str
    observado: pd.Series
    previsto: pd.DataFrame
    metricas: dict[str, float]
    cobertura: dict[int, float]
    backtest: dict[str, float]


def _ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding='utf-8'))


def decisoes_aprovadas(raiz: Path) -> dict[str, str]:
    """Id -> tipo das decisões cujo último evento é `approved`."""
    tipos: dict[str, str] = {}
    ultimo: dict[str, str] = {}
    for linha in (
        (raiz / '.ds-workflow/decisions.jsonl')
        .read_text(encoding='utf-8')
        .splitlines()
    ):
        if not linha.strip():
            continue
        evento = json.loads(linha)
        if 'kind' in evento:
            tipos[evento['id']] = evento['kind']
        ultimo[evento['id']] = evento['event']
    return {i: tipos.get(i, '') for i, e in ultimo.items() if e == 'approved'}


def verificar_gates(raiz: Path, protocolo: Path = PROTOCOLO) -> None:
    """Fase, protocolo congelado e decisões aprovadas, ou `ValueError`."""
    estado = _ler_json(raiz / '.ds-workflow/state.json')
    problemas = []
    if estado.get('phase') != 'final_evaluation':
        problemas.append(f'fase {estado.get("phase")!r}, não final_evaluation')
    congelado = estado.get('frozen', {}).get('evaluation_protocol')
    arquivo = raiz / protocolo
    if congelado is None:
        problemas.append('evaluation_protocol não congelado')
    elif (
        hashlib.sha256(arquivo.read_bytes()).hexdigest() != congelado['sha256']
    ):
        problemas.append('o protocolo mudou depois de congelado')
    aprovadas = decisoes_aprovadas(raiz)
    problemas += [
        f'{i} não aprovada' for i in DECISOES_EXIGIDAS if i not in aprovadas
    ]
    if 'final_evaluation' not in aprovadas.values():
        problemas.append('sem decisão final_evaluation aprovada')
    if problemas:
        raise ValueError('Portões não cumpridos: ' + '; '.join(problemas))


def registrar_tentativa(caminho: Path) -> None:
    """Marca a tentativa de forma exclusiva; a marca nunca é apagada."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        with caminho.open('x', encoding='utf-8') as arquivo:
            json.dump(
                {
                    'iniciada_em': datetime.now(UTC).isoformat(),
                    'estado': 'iniciada',
                },
                arquivo,
            )
    except FileExistsError as erro:
        raise ValueError(
            f'A avaliação final já foi iniciada ({caminho}); o OOT não é '
            'aberto de novo.'
        ) from erro


def _atualizar_tentativa(caminho: Path, **campos) -> None:
    dados = _ler_json(caminho) | campos
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')


def resolver_selecionados(cfg: Settings) -> list[Selecionado]:
    """Os oito `selecionado`, conferidos; qualquer falha aborta sem OOT."""
    cliente = mlflow_cliente.conectar(cfg)
    particoes = {(p.sku, p.granularidade): p for p in carregar_particoes(cfg)}
    selecionados = []
    for granularidade in GRANULARIDADES:
        for sku in SKUS:
            nome = nome_modelo(sku, granularidade)
            versao = cliente.get_model_version_by_alias(
                nome, ALIAS_SELECIONADO
            )
            tags = cliente.get_run(versao.run_id).data.tags
            if (tags.get('sku'), tags.get('granularidade')) != (
                sku,
                granularidade,
            ):
                raise ModeloRecusado(
                    f'{nome}: versão {versao.version} é de outra série'
                )
            particao = particoes[sku, granularidade]
            passos = (particao.oot_fim - particao.oot_inicio).days
            passos = passos // DIAS_POR_PERIODO[granularidade] + 1
            if passos != horizonte_maximo(cfg, granularidade):
                raise ValueError(
                    f'{nome}: OOT de {passos} períodos, esperado '
                    f'{horizonte_maximo(cfg, granularidade)}'
                )
            selecionados.append(
                Selecionado(
                    sku=sku,
                    granularidade=granularidade,
                    versao=versao,
                    algoritmo=versao.tags.get('algoritmo', ''),
                    run_id=versao.run_id,
                    modelo=mlflow_cliente.carregar_conferido(versao),
                    particao=particao,
                    desenvolvimento=carregar_serie(cfg, sku, granularidade),
                )
            )
    return selecionados


def ler_oot(cfg: Settings, selecionados: list[Selecionado]) -> dict:
    """Única leitura do OOT: (sku, granularidade) -> série observada."""
    observados = {}
    with duckdb.connect(str(cfg.oot_db_path), read_only=True) as con:
        for s in selecionados:
            tabela, coluna = _TABELAS_OOT[s.granularidade]
            linhas = con.execute(
                f'SELECT {coluna}, quantidade FROM {tabela} WHERE sku = ? '
                f'ORDER BY {coluna}',
                [s.sku],
            ).fetchall()
            datas, quantidades = zip(*linhas, strict=True)
            observados[s.sku, s.granularidade] = pd.Series(
                [float(q) for q in quantidades],
                index=pd.DatetimeIndex(datas),
                name='quantidade',
            )
    return observados


def cobertura(observado, inferior, superior) -> float:
    """Fração observada dentro dos limites inclusivos; `nan` sem limites."""
    inferior = np.asarray(inferior, dtype=float)
    superior = np.asarray(superior, dtype=float)
    if np.isnan(inferior).any() or np.isnan(superior).any():
        return float('nan')
    observado = np.asarray(observado, dtype=float)
    return float(np.mean((observado >= inferior) & (observado <= superior)))


def medir(
    observado, previsto: pd.DataFrame, escala: float
) -> tuple[dict[str, float], dict[int, float]]:
    """Métricas do ADR 0002 e cobertura dos intervalos de 80% e 95%."""
    medidas = metricas.calcular_com_escala(
        observado, previsto['previsao'], escala
    )
    cobertas = {
        n: cobertura(
            observado, previsto[f'inferior_{n}'], previsto[f'superior_{n}']
        )
        for n in NIVEIS
    }
    return medidas, cobertas


def avaliar(
    selecionado: Selecionado, observado: pd.Series, cliente: MlflowClient
) -> ResultadoOot:
    horizonte = len(observado)
    previsto = selecionado.modelo.unwrap_python_model().prever_com_intervalos(
        horizonte
    )
    medidas, cobertas = medir(
        observado.to_numpy(),
        previsto,
        metricas.escala_mase(selecionado.desenvolvimento),
    )
    run = cliente.get_run(selecionado.run_id)
    chaves = (*metricas.METRICAS, 'cobertura_80', 'cobertura_95')
    return ResultadoOot(
        sku=selecionado.sku,
        granularidade=selecionado.granularidade,
        versao=str(selecionado.versao.version),
        algoritmo=selecionado.algoritmo,
        run_id=selecionado.run_id,
        observado=observado,
        previsto=previsto,
        metricas=medidas,
        cobertura=cobertas,
        backtest={k: run.data.metrics.get(k, float('nan')) for k in chaves},
    )


def _sem_nan(valores) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in valores]


def registrar_resultado(
    cliente: MlflowClient, resultado: ResultadoOot, selecionado: Selecionado
) -> None:
    """Grava no run da versão avaliada; métrica indefinida não é gravada."""
    run_id = resultado.run_id
    indefinidas = []
    valores = {f'oot_{m}': v for m, v in resultado.metricas.items()}
    valores |= {
        f'oot_cobertura_{n}': v for n, v in resultado.cobertura.items()
    }
    for chave, valor in valores.items():
        if np.isnan(valor):
            indefinidas.append(chave)
        else:
            cliente.log_metric(run_id, chave, valor)
    cliente.set_tag(run_id, 'oot_avaliado', 'true')
    if indefinidas:
        cliente.set_tag(
            run_id, 'oot_metricas_indefinidas', ','.join(sorted(indefinidas))
        )
    cliente.log_dict(
        run_id,
        {
            'datas': [d.date().isoformat() for d in resultado.observado.index],
            'observado': resultado.observado.tolist(),
            'previsao': _sem_nan(resultado.previsto['previsao']),
            **{
                f'{lado}_{n}': _sem_nan(resultado.previsto[f'{lado}_{n}'])
                for n in NIVEIS
                for lado in ('inferior', 'superior')
            },
            'metricas': {
                k: None if np.isnan(v) else v for k, v in valores.items()
            },
        },
        ARTEFATO_OOT,
    )
    backtest = mlflow.artifacts.load_dict(f'runs:/{run_id}/backtest.json')
    figura = graficos.desenhar(
        selecionado.desenvolvimento,
        selecionado.particao,
        backtest['folds'],
        resultado.previsto,
        f'{resultado.sku} {resultado.granularidade}: '
        f'{resultado.algoritmo} (OOT aberto)',
        oot_observado=resultado.observado,
    )
    cliente.log_figure(run_id, figura, ARTEFATO_GRAFICO_OOT)
    plt.close(figura)


def _fmt(valor: float) -> str:
    return (
        'indefinida' if np.isnan(valor) else f'{valor:.3f}'.replace('.', ',')
    )


def relatorio_markdown(resultados: list[ResultadoOot]) -> str:
    linhas = [
        '# Avaliação final no OOT (#13)',
        '',
        'Uma única abertura do OOT, conforme '
        '`docs/analysis/protocolo-avaliacao-final.md`. Comparação '
        'descritiva com a média do backtest do mesmo run; sem teste de '
        'hipótese, sem intervalo de confiança e sem confiança de modelo '
        '(D-020). O MASE do OOT usa a escala do naive de um passo de todo '
        'o desenvolvimento; o do backtest usa a de cada treino de fold, '
        'logo os dois MASE não são diretamente comparáveis.',
        '',
        '| Série | Algoritmo (versão) | Períodos | MAE OOT / backtest | '
        'RMSE OOT / backtest | WAPE OOT / backtest | MASE OOT / backtest | '
        'Cobertura 80% OOT / backtest | Cobertura 95% OOT / backtest |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for r in resultados:
        m, b, c = r.metricas, r.backtest, r.cobertura
        linhas.append(
            f'| {r.sku} {r.granularidade} | {r.algoritmo} ({r.versao}) | '
            f'{len(r.observado)} | {_fmt(m["mae"])} / {_fmt(b["mae"])} | '
            f'{_fmt(m["rmse"])} / {_fmt(b["rmse"])} | '
            f'{_fmt(m["wape"])} / {_fmt(b["wape"])} | '
            f'{_fmt(m["mase"])} / {_fmt(b["mase"])} | '
            f'{_fmt(c[80])} / {_fmt(b["cobertura_80"])} | '
            f'{_fmt(c[95])} / {_fmt(b["cobertura_95"])} |'
        )
    linhas += [
        '',
        '## Limitações',
        '',
        '- Séries semanais têm 2 pontos no OOT: servem para notar degradação '
        'grosseira, não como evidência estatística (ADR 0002).',
        '- Séries diárias têm 14 pontos, autocorrelacionados; a cobertura '
        'observada tem granularidade de 1/14.',
        '- Nenhum `champion` foi atribuído: a publicação por série é decisão '
        'do usuário (`case-mr-health promover`).',
    ]
    return '\n'.join(linhas) + '\n'


def avaliar_final(
    cfg: Settings,
    raiz: Path = Path(),
    relatorio_path: Path = RELATORIO,
) -> list[ResultadoOot]:
    """Roda a avaliação final uma única vez."""
    verificar_gates(raiz)
    marca = raiz / '.ds-workflow/final-evaluation-attempt.json'
    if marca.exists():
        raise ValueError(
            f'A avaliação final já foi iniciada ({marca}); o OOT não é '
            'aberto de novo.'
        )
    selecionados = resolver_selecionados(cfg)
    registrar_tentativa(marca)
    try:
        resultados = _executar(cfg, selecionados, relatorio_path)
    except Exception as erro:
        _atualizar_tentativa(marca, estado='falhou', erro=str(erro))
        raise
    _atualizar_tentativa(marca, estado='concluida')
    return resultados


def _executar(
    cfg: Settings, selecionados: list[Selecionado], relatorio_path: Path
) -> list[ResultadoOot]:
    observados = ler_oot(cfg, selecionados)
    cliente = MlflowClient()
    resultados = []
    for s in selecionados:
        resultado = avaliar(s, observados[s.sku, s.granularidade], cliente)
        registrar_resultado(cliente, resultado, s)
        resultados.append(resultado)
        logger.info(
            '{} {}: MAE {} cobertura 80% {} 95% {}',
            s.sku,
            s.granularidade,
            _fmt(resultado.metricas['mae']),
            _fmt(resultado.cobertura[80]),
            _fmt(resultado.cobertura[95]),
        )
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(relatorio_markdown(resultados), encoding='utf-8')
    return resultados


def promover(  # noqa: PLR0913, PLR0917
    cfg: Settings,
    sku: str,
    granularidade: str,
    versao: str,
    decisao: str,
    raiz: Path = Path(),
) -> None:
    """Atribui `champion` a uma versão já avaliada, com decisão aprovada."""
    if decisao not in decisoes_aprovadas(raiz):
        raise ValueError(f'Decisão {decisao} não está aprovada')
    cliente = mlflow_cliente.conectar(cfg)
    nome = nome_modelo(sku, granularidade)
    registrada = cliente.get_model_version(nome, versao)
    tags = cliente.get_run(registrada.run_id).data.tags
    if (tags.get('sku'), tags.get('granularidade')) != (sku, granularidade):
        raise ValueError(
            f'Versão {versao} não é da série {sku}/{granularidade}'
        )
    if tags.get('oot_avaliado') != 'true':
        raise ValueError(
            f'Versão {versao} não passou pela avaliação final no OOT'
        )
    cliente.set_registered_model_alias(
        nome, mlflow_cliente.ALIAS_CHAMPION, versao
    )
    logger.info('{}: versão {} é champion (decisão {})', nome, versao, decisao)
