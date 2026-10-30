"""Treino de uma série: backtest, métricas e registro no MLflow (#7).

Para cada candidato da tabela do #6 que tenha implementação em
`algoritmos.ALGORITMOS`, e para cada combinação de hiperparâmetros, abre
uma execução (run) no experimento da granularidade, registra o backtest e
o modelo ajustado com todo o desenvolvimento como uma versão de
`demanda-<sku>-<granularidade>` (ADR 0005). A escolha da versão que serve
a série é do #12/#13: aqui nenhum modelo é selecionado. Os intervalos
(#8) ficam em `intervalos.py`; aqui só se registram e se expõem no modelo.
"""

import hashlib
import json
import random
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from importlib import metadata
from itertools import product
from pathlib import Path
from zoneinfo import ZoneInfo

import mlflow
import mlflow.pyfunc
import numpy as np
import pandas as pd
from loguru import logger
from mlflow import MlflowClient

from case_mr_health import algoritmos, intervalos, metricas
from case_mr_health.algoritmos_statsmodels import (
    DiagnosticoAjuste,
    FalhaConvergencia,
    coletar_diagnosticos,
)
from case_mr_health.backtest import ResultadoBacktest, rodar_backtest
from case_mr_health.candidatos import (
    NAO_ATENDIDA,
    NAO_TESTAVEL,
    SKUS,
    Candidato,
    candidatos,
)
from case_mr_health.config import Settings
from case_mr_health.intervalos import Calibracao, ConfigIntervalos, rotulo
from case_mr_health.particoes import (
    GRANULARIDADES,
    Particao,
    abrir_desenvolvimento,
    carregar_particoes,
)

PREFIXO_EXPERIMENTO = 'demanda'
CAMINHO_MODELO = 'modelo'
ARTEFATO_DIAGNOSTICOS = 'diagnosticos.json'
ARTEFATO_BACKTEST = 'backtest.json'
LIMITE_TAG = 5000
_COLUNA_DATA = {
    'diaria': ('serie_diaria', 'data'),
    'semanal': (
        'serie_semanal',
        'semana',
    ),
}


@dataclass(frozen=True)
class Contexto:
    """O que é comum a todos os runs de uma série."""

    cfg: Settings
    experimento_id: str
    serie: pd.Series
    particao: Particao
    seed: int
    codigo: dict[str, str]
    rodada: str = ''


@dataclass(frozen=True)
class ResumoRun:
    run_id: str
    algoritmo: str
    papel: str
    hiperparametros: dict
    medias: dict[str, float]
    versao_modelo: str
    hash_artefato: str
    intervalo_metodo: str = ''
    cobertura: dict[float, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResumoFalha:
    """Combinação que não convergiu; o run existe, sem métricas nem versão."""

    run_id: str
    algoritmo: str
    papel: str
    hiperparametros: dict
    ajuste: str  # `fold_<i>` ou `modelo_final`
    motivo: str


@dataclass(frozen=True)
class ResumoTreino:
    sku: str
    granularidade: str
    seed: int
    runs: tuple[ResumoRun, ...]
    sem_implementacao: tuple[str, ...]
    falhas: tuple[ResumoFalha, ...] = ()
    rodada: str = ''


def nome_modelo(sku: str, granularidade: str) -> str:
    """`demanda-<sku>-<granularidade>`, SKU em minúsculas e sem espaço."""
    slug = sku.lower().replace(' ', '-')
    return f'{PREFIXO_EXPERIMENTO}-{slug}-{granularidade}'


def nome_experimento(granularidade: str) -> str:
    return f'{PREFIXO_EXPERIMENTO}-{granularidade}'


def normalizar_sku(sku: str) -> str:
    """Aceita `item A` ou só a letra (`A`)."""
    letra = sku.strip().upper().removeprefix('ITEM').strip()
    candidato = f'item {letra}'
    if candidato not in SKUS:
        raise ValueError(f'SKU desconhecido: {sku}; use um de {SKUS}')
    return candidato


def seed_padrao(cfg: Settings, agora: datetime | None = None) -> int:
    """Seed efetiva: a configurada ou a data local de hoje, `YYYYMMDD`."""
    if cfg.seed is not None:
        return cfg.seed
    fuso = ZoneInfo(cfg.fuso_horario)
    agora = agora.astimezone(fuso) if agora else datetime.now(fuso)
    return int(agora.strftime('%Y%m%d'))


def aplicar_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)  # noqa: NPY002


def carregar_serie(cfg: Settings, sku: str, granularidade: str) -> pd.Series:
    """Série da visão de desenvolvimento (o OOT não está nesse arquivo)."""
    tabela, coluna = _COLUNA_DATA[granularidade]
    con = abrir_desenvolvimento(cfg)
    try:
        linhas = con.execute(
            f'SELECT {coluna}, quantidade FROM {tabela} WHERE sku = ? '
            f'ORDER BY {coluna}',
            [sku],
        ).fetchall()
    finally:
        con.close()
    if not linhas:
        raise ValueError(f'Série {sku}/{granularidade} sem dados')
    datas, quantidades = zip(*linhas, strict=True)
    return pd.Series(
        [float(q) for q in quantidades],
        index=pd.DatetimeIndex(datas),
        name='quantidade',
    )


def versao_codigo() -> dict[str, str]:
    """Versão do pacote e, quando há git, o commit e se a árvore está suja."""
    info = {'pacote': metadata.version('case-mr-health')}
    try:
        info['commit'] = _git('rev-parse', 'HEAD')
        info['arvore_suja'] = str(bool(_git('status', '--porcelain')))
    except OSError, subprocess.CalledProcessError:
        info['commit'] = 'desconhecido'
    return info


def _git(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        ['git', *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def hash_artefato(diretorio: Path) -> str:
    """SHA-256 dos arquivos do diretório (caminho relativo + conteúdo)."""
    resumo = hashlib.sha256()
    for arquivo in sorted(p for p in diretorio.rglob('*') if p.is_file()):
        resumo.update(arquivo.relative_to(diretorio).as_posix().encode())
        resumo.update(arquivo.read_bytes())
    return resumo.hexdigest()


class ModeloDemanda(mlflow.pyfunc.PythonModel):
    """Modelo servível: recebe `horizonte`, devolve previsão não negativa.

    Sem mais colunas, devolve o vetor da previsão. Com a coluna
    `intervalos` verdadeira, devolve o `DataFrame` de
    `prever_com_intervalos`, com uma linha por período futuro.
    """

    def __init__(
        self,
        previsor: algoritmos.Previsor,
        calibracao: Calibracao | None = None,
    ):
        self.previsor = previsor
        self.calibracao = calibracao

    def predict(self, context, model_input, params=None):
        horizonte = int(model_input['horizonte'].iloc[0])
        if 'intervalos' in model_input and model_input['intervalos'].iloc[0]:
            return self.prever_com_intervalos(horizonte)
        return np.clip(self.previsor.prever(horizonte), 0, None)

    def prever_com_intervalos(self, horizonte: int) -> pd.DataFrame:
        """Colunas `previsao`, `inferior_<nível>` e `superior_<nível>`.

        Exemplo: `inferior_80`. Limites não negativos, aninhados e contendo
        a previsão; `nan` se o método da versão é `indisponivel`. Falha
        acima do horizonte calibrado, que não foi validado.
        """
        if self.calibracao is None:
            raise ValueError('modelo sem calibração de intervalos')
        previsto = np.clip(self.previsor.prever(horizonte), 0, None)
        limites = intervalos.normalizar(
            previsto,
            self.calibracao.limites(self.previsor, previsto, horizonte),
            self.calibracao.fracao_zeros,
        )
        colunas = {'previsao': previsto}
        for nivel, (inferior, superior) in limites.items():
            colunas[f'inferior_{rotulo(nivel)}'] = inferior
            colunas[f'superior_{rotulo(nivel)}'] = superior
        return pd.DataFrame(colunas)


def _preparar_mlflow(cfg: Settings, granularidade: str) -> str:
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    cfg.mlflow_artifact_dir.mkdir(parents=True, exist_ok=True)
    nome = nome_experimento(granularidade)
    experimento = mlflow.get_experiment_by_name(nome)
    if experimento is not None:
        return experimento.experiment_id
    return mlflow.create_experiment(
        nome, artifact_location=cfg.mlflow_artifact_dir.resolve().as_uri()
    )


def treinar_serie(
    cfg: Settings,
    sku: str,
    granularidade: str,
    seed: int | None = None,
    rodada: str = '',
) -> ResumoTreino:
    """Treina todos os candidatos implementados de uma série.

    `rodada` identifica a execução nas tags dos runs: a seleção do #12 lê
    só uma rodada, sem misturar versões de execuções anteriores.
    """
    if granularidade not in GRANULARIDADES:
        raise ValueError(f'granularidade desconhecida: {granularidade}')
    sku = normalizar_sku(sku)
    seed = seed if seed is not None else seed_padrao(cfg)
    aplicar_seed(seed)
    contexto = Contexto(
        cfg,
        _preparar_mlflow(cfg, granularidade),
        carregar_serie(cfg, sku, granularidade),
        _particao(cfg, sku, granularidade),
        seed,
        versao_codigo(),
        rodada,
    )

    runs, falhas, pendentes = [], [], []
    for candidato in candidatos(sku, granularidade):
        if not candidato.entra:
            continue
        if candidato.algoritmo not in algoritmos.ALGORITMOS:
            pendentes.append(candidato.algoritmo)
            continue
        for hiperparametros in candidato.combinacoes():
            resultado = _treinar_monitorado(
                contexto, candidato, hiperparametros
            )
            destino = falhas if isinstance(resultado, ResumoFalha) else runs
            destino.append(resultado)
    if pendentes:
        logger.warning(
            '{}/{}: sem implementação, não treinados: {}',
            sku,
            granularidade,
            ', '.join(pendentes),
        )
    return ResumoTreino(
        sku,
        granularidade,
        seed,
        tuple(runs),
        tuple(pendentes),
        tuple(falhas),
        rodada,
    )


def treinar_todas(
    cfg: Settings,
    seed: int | None = None,
    series: tuple[tuple[str, str], ...] | None = None,
) -> tuple[str, list[ResumoTreino]]:
    """Treina cada série de forma independente, numa mesma rodada."""
    rodada = uuid.uuid4().hex
    seed = seed if seed is not None else seed_padrao(cfg)
    todas = series or tuple(product(SKUS, GRANULARIDADES))
    return rodada, [
        treinar_serie(cfg, sku, granularidade, seed, rodada)
        for sku, granularidade in todas
    ]


def _particao(cfg: Settings, sku: str, granularidade: str) -> Particao:
    for p in carregar_particoes(cfg):
        if (p.sku, p.granularidade) == (sku, granularidade):
            return p
    raise ValueError(f'Série {sku}/{granularidade} sem partição')


def _treinar_monitorado(
    ctx: Contexto, candidato: Candidato, hiperparametros: dict
) -> ResumoRun | ResumoFalha:
    """Uma combinação; falha de convergência vira run, nunca exceção.

    Basta um fold (ou o ajuste final) falhar para a combinação inteira
    falhar: média de menos folds não é comparável com a dos outros (ADR 0010).
    """
    with coletar_diagnosticos() as diagnosticos:
        try:
            resumo = _treinar_candidato(
                ctx, candidato.algoritmo, candidato.papel, hiperparametros
            )
        except FalhaConvergencia as falha:
            return _registrar_falha(
                ctx, candidato, hiperparametros, falha, diagnosticos
            )
    if diagnosticos:
        _registrar_diagnosticos(ctx, resumo.run_id, diagnosticos)
    return resumo


def _rotulo_ajuste(ctx: Contexto, n_treino: int) -> str:
    """Identifica o ajuste pelo tamanho do treino (janela expansiva)."""
    if n_treino == len(ctx.serie):
        return 'modelo_final'
    indice = pd.DatetimeIndex(ctx.serie.index).normalize()
    for i, fold in enumerate(ctx.particao.folds, start=1):
        if n_treino == (indice <= pd.Timestamp(fold.treino_fim)).sum():
            return f'fold_{i}'
    return f'ajuste_n{n_treino}'


def _ajustes_do_backtest(
    ctx: Contexto, diagnosticos: list[DiagnosticoAjuste]
) -> list[tuple[str, DiagnosticoAjuste]]:
    """Folds e modelo final, sem os ajustes extras da calibração (#8).

    A calibração ajusta em treinos muito curtos, que não dizem nada sobre
    as premissas do modelo avaliado, e repete tamanhos de fold.
    """
    ajustes: dict[str, DiagnosticoAjuste] = {}
    for d in diagnosticos:
        rotulo = _rotulo_ajuste(ctx, d.n_treino)
        if not rotulo.startswith('ajuste_n'):
            ajustes.setdefault(rotulo, d)
    return list(ajustes.items())


def _payload_diagnosticos(
    ctx: Contexto, diagnosticos: list[DiagnosticoAjuste]
) -> dict:
    return {
        'ajustes': [
            {'ajuste': rotulo, **asdict(d)}
            for rotulo, d in _ajustes_do_backtest(ctx, diagnosticos)
        ]
    }


def _premissas_em(diagnosticos: list[DiagnosticoAjuste], situacao: str) -> str:
    return ','.join(
        sorted({
            p.premissa
            for d in diagnosticos
            for p in d.premissas
            if p.situacao == situacao
        })
    )


def _registrar_diagnosticos(
    ctx: Contexto, run_id: str, diagnosticos: list[DiagnosticoAjuste]
) -> None:
    cliente = MlflowClient()
    cliente.log_dict(
        run_id,
        _payload_diagnosticos(ctx, diagnosticos),
        ARTEFATO_DIAGNOSTICOS,
    )
    principais = [d for _, d in _ajustes_do_backtest(ctx, diagnosticos)]
    cliente.set_tag(
        run_id,
        'premissas_nao_atendidas',
        _premissas_em(principais, NAO_ATENDIDA),
    )
    cliente.set_tag(
        run_id,
        'premissas_nao_testaveis',
        _premissas_em(principais, NAO_TESTAVEL),
    )


def _registrar_falha(
    ctx: Contexto,
    candidato: Candidato,
    hiperparametros: dict,
    falha: FalhaConvergencia,
    diagnosticos: list[DiagnosticoAjuste],
) -> ResumoFalha:
    """Abre um run `FAILED`, sem métricas e sem versão de modelo."""
    ajuste = _rotulo_ajuste(ctx, falha.n_treino)
    texto_hp = json.dumps(hiperparametros, default=str)
    run = mlflow.start_run(
        experiment_id=ctx.experimento_id,
        run_name=f'{candidato.algoritmo}-{texto_hp}',
    )
    try:
        mlflow.set_tags({
            'sku': ctx.particao.sku,
            'granularidade': ctx.particao.granularidade,
            'algoritmo': candidato.algoritmo,
            'papel': candidato.papel,
            'falha_convergencia': 'true',
            'falha_ajuste': ajuste,
            'falha_motivo': falha.motivo[:LIMITE_TAG],
            **_tag_rodada(ctx),
        })
        _registrar_parametros(ctx, hiperparametros)
        mlflow.log_dict(
            _payload_diagnosticos(ctx, diagnosticos), ARTEFATO_DIAGNOSTICOS
        )
    finally:
        mlflow.end_run(status='FAILED')
    logger.warning(
        '{}/{}: {} {} não convergiu em {}: {}',
        ctx.particao.sku,
        ctx.particao.granularidade,
        candidato.algoritmo,
        texto_hp,
        ajuste,
        falha.motivo,
    )
    return ResumoFalha(
        run.info.run_id,
        candidato.algoritmo,
        candidato.papel,
        hiperparametros,
        ajuste,
        falha.motivo,
    )


def requisitos_pip(previsor: algoritmos.Previsor) -> list[str]:
    """Dependências do previsor com as versões instaladas (do pickle)."""
    return [
        f'{nome}=={metadata.version(nome)}'
        for nome in getattr(previsor, 'dependencias', ('numpy',))
    ]


def horizonte_maximo(cfg: Settings, granularidade: str) -> int:
    """Maior horizonte servido: o tamanho do OOT (glossário, #14)."""
    if granularidade == 'diaria':
        return cfg.oot_diaria_dias
    return cfg.oot_semanal_semanas


def _config_intervalos(cfg: Settings) -> ConfigIntervalos:
    return ConfigIntervalos(cfg.niveis_intervalo, cfg.intervalo_max_origens)


def _calibrar_final(
    ctx: Contexto, algoritmo: str, hiperparametros: dict, usar_nativo: bool
) -> Calibracao:
    """Calibração do modelo final: todo o desenvolvimento, sem o OOT."""
    config = _config_intervalos(ctx.cfg)
    horizonte = horizonte_maximo(ctx.cfg, ctx.particao.granularidade)
    y = ctx.serie.to_numpy(dtype=float)
    if usar_nativo:
        return intervalos.nativa(config.niveis, horizonte, y)
    return intervalos.calibrar(
        lambda: algoritmos.criar(algoritmo, hiperparametros, ctx.seed),
        y,
        horizonte,
        config,
    )


def _treinar_candidato(
    ctx: Contexto, algoritmo: str, papel: str, hiperparametros: dict
) -> ResumoRun:
    particao, seed = ctx.particao, ctx.seed
    aplicar_seed(seed)
    resultado = rodar_backtest(
        ctx.serie,
        particao,
        algoritmo,
        hiperparametros,
        seed,
        _config_intervalos(ctx.cfg),
    )
    modelo_final = algoritmos.criar(algoritmo, hiperparametros, seed).ajustar(
        ctx.serie.to_numpy(dtype=float)
    )
    calibracao = _calibrar_final(
        ctx, algoritmo, hiperparametros, resultado.intervalos.usar_nativo
    )
    nome = nome_modelo(particao.sku, particao.granularidade)
    with mlflow.start_run(
        experiment_id=ctx.experimento_id,
        run_name=f'{algoritmo}-{json.dumps(hiperparametros, default=str)}',
    ) as run:
        mlflow.set_tags({
            'sku': particao.sku,
            'granularidade': particao.granularidade,
            'algoritmo': algoritmo,
            'papel': papel,
            **_tag_rodada(ctx),
        })
        _registrar_parametros(ctx, hiperparametros)
        _registrar_metricas(resultado)
        _registrar_intervalos(resultado, calibracao)
        mlflow.log_dict(_payload_backtest(resultado), ARTEFATO_BACKTEST)
        info = mlflow.pyfunc.log_model(
            name=CAMINHO_MODELO,
            python_model=ModeloDemanda(modelo_final, calibracao),
            registered_model_name=nome,
            pip_requirements=requisitos_pip(modelo_final),
        )
        artefato = Path(mlflow.artifacts.download_artifacts(info.model_uri))
        hash_modelo = hash_artefato(artefato)
        mlflow.set_tag('hash_artefato', hash_modelo)
        MlflowClient().set_model_version_tag(
            nome, info.registered_model_version, 'hash_artefato', hash_modelo
        )
        for chave, valor in {
            'algoritmo': algoritmo,
            'hiperparametros': json.dumps(hiperparametros, default=str),
            'run_id': run.info.run_id,
            'intervalo_metodo': calibracao.metodo,
            'intervalo_niveis': json.dumps(calibracao.niveis),
            'intervalo_horizonte': str(calibracao.horizonte),
        }.items():
            MlflowClient().set_model_version_tag(
                nome, info.registered_model_version, chave, valor
            )
    return ResumoRun(
        run.info.run_id,
        algoritmo,
        papel,
        hiperparametros,
        resultado.medias,
        str(info.registered_model_version),
        hash_modelo,
        calibracao.metodo,
        {n: c.valor for n, c in resultado.intervalos.usada.items()},
    )


def _tag_rodada(ctx: Contexto) -> dict[str, str]:
    return {'rodada': ctx.rodada} if ctx.rodada else {}


def _sem_nan(valores) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in valores]


def _payload_backtest(resultado: ResultadoBacktest) -> dict:
    """Previsão por fold, com os limites do método usado, para os gráficos."""
    usar_nativo = resultado.intervalos.usar_nativo
    folds = []
    for r in resultado.folds:
        fold = {
            'fold': r.fold,
            'teste_inicio': r.teste_inicio.isoformat(),
            'teste_fim': r.teste_fim.isoformat(),
            'observado': list(r.observado),
            'previsto': list(r.previsto),
        }
        limites = r.intervalos.empirico
        if usar_nativo and r.intervalos.nativo is not None:
            limites = r.intervalos.nativo
        for nivel, (inferior, superior) in limites.items():
            fold[f'inferior_{rotulo(nivel)}'] = _sem_nan(inferior)
            fold[f'superior_{rotulo(nivel)}'] = _sem_nan(superior)
        folds.append(fold)
    return {'folds': folds}


def _registrar_parametros(ctx: Contexto, hiperparametros: dict) -> None:
    particao = ctx.particao
    mlflow.log_params({f'hp.{k}': v for k, v in hiperparametros.items()})
    mlflow.log_params({
        'seed': ctx.seed,
        'n_observacoes': len(ctx.serie),
        'n_folds': len(particao.folds),
        'desenvolvimento_inicio': particao.desenvolvimento_inicio,
        'desenvolvimento_fim': particao.desenvolvimento_fim,
        'oot_inicio': particao.oot_inicio,
        'oot_fim': particao.oot_fim,
        **{f'codigo.{k}': v for k, v in ctx.codigo.items()},
    })
    for i, fold in enumerate(particao.folds, start=1):
        mlflow.log_params({
            f'fold_{i}.treino': f'{fold.treino_inicio}/{fold.treino_fim}',
            f'fold_{i}.teste': f'{fold.teste_inicio}/{fold.teste_fim}',
        })
    mlflow.log_dict(json.loads(ctx.cfg.model_dump_json()), 'config.json')


def _registrar_metricas(resultado: ResultadoBacktest) -> None:
    indefinidas = []
    for m in metricas.METRICAS:
        for r in resultado.folds:
            _metrica(f'{m}_fold', r.metricas[m], r.fold, indefinidas)
        _metrica(m, resultado.medias[m], None, indefinidas)
        valores = [r.metricas[m] for r in resultado.folds]
        _metrica(
            f'{m}_dp',
            float(np.std(valores, ddof=1))
            if len(valores) > 1
            else float('nan'),
            None,
            indefinidas,
        )
    for variante, medias in resultado.sensibilidade.items():
        for m, valor in medias.items():
            _metrica(f'sens_{variante}_{m}', valor, None, indefinidas)
    observado = np.concatenate([r.observado for r in resultado.folds])
    previsto = np.concatenate([r.previsto for r in resultado.folds])
    vies = float(np.mean(previsto - observado))
    _metrica('vies', vies, None, indefinidas)
    if observado.mean() > 0:
        _metrica('vies_relativo', vies / observado.mean(), None, indefinidas)
    if indefinidas:
        mlflow.set_tag(
            'metricas_indefinidas', ','.join(sorted(set(indefinidas)))
        )


def _registrar_intervalos(
    resultado: ResultadoBacktest, calibracao: Calibracao
) -> None:
    """Método usado e cobertura do backtest (a do OOT é do #13)."""
    resumo = resultado.intervalos
    mlflow.set_tags({
        'intervalo_metodo': calibracao.metodo,
        'intervalo_motivo': resumo.motivo,
    })
    mlflow.log_params({
        'intervalo.niveis': json.dumps(calibracao.niveis),
        'intervalo.horizonte': calibracao.horizonte,
        'intervalo.n_erros': calibracao.n_erros,
        'intervalo.n_origens': calibracao.n_origens,
        'intervalo.n_falhas': calibracao.n_falhas,
        'intervalo.fracao_zeros': calibracao.fracao_zeros,
    })
    for i, metodo in enumerate(resumo.metodos_fold, start=1):
        mlflow.log_param(f'fold_{i}.intervalo_metodo', metodo)
    indefinidas = []
    for nivel, cobertura in resumo.usada.items():
        nome = rotulo(nivel)
        valores = {
            f'cobertura_{nome}': cobertura.valor,
            f'cobertura_{nome}_ic_inf': cobertura.ic[0],
            f'cobertura_{nome}_ic_sup': cobertura.ic[1],
            f'amplitude_{nome}': resumo.amplitude[nivel],
            f'cobertura_empirico_{nome}': resumo.empirico[nivel].valor,
        }
        if resumo.nativo is not None:
            valores[f'cobertura_nativo_{nome}'] = resumo.nativo[nivel].valor
        if resumo.sem_atipico:
            valores[f'sens_sem_periodo_atipico_cobertura_{nome}'] = (
                resumo.sem_atipico[nivel].valor
            )
        for chave, valor in valores.items():
            _metrica(chave, valor, None, indefinidas)
        for passo, parcial in enumerate(resumo.por_fold[nivel], start=1):
            _metrica(
                f'cobertura_{nome}_fold', parcial.valor, passo, indefinidas
            )
    mlflow.log_metric(
        'cobertura_n_pontos', next(iter(resumo.usada.values())).n
    )
    if indefinidas:
        mlflow.set_tag(
            'intervalo_metricas_indefinidas',
            ','.join(sorted(set(indefinidas))),
        )


def _metrica(chave, valor, passo, indefinidas) -> None:
    if np.isnan(valor):
        indefinidas.append(chave)
        return
    mlflow.log_metric(chave, valor, step=passo)
