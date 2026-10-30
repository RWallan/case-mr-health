"""Intervalos de previsão e cobertura empírica (#8).

Regras em `docs/analysis/plano-intervalos.md` (fixadas antes de ver a
cobertura em dados reais) e no ADR 0007. Resumo:

- o mecanismo empírico usa apenas `ajustar` e `prever`, logo serve a
  qualquer `Previsor` sem código novo: gera erros de 1 a `h` passos por
  origem móvel dentro do treino, sem nenhum dado do teste;
- `intervalos_nativos` é opcional e detectado por duck typing; o nativo só
  é usado se passar por `decidir_nativo`;
- truncar em zero, aplicar o piso zero (D-009), conter a previsão e
  aninhar os níveis ficam aqui (`normalizar`), nunca no previsor.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil, floor, sqrt

import numpy as np
from loguru import logger
from scipy import stats

from case_mr_health.algoritmos import Previsor

NATIVO = 'nativo'
QUANTIL = 'empirico_quantil'
STUDENT = 'empirico_t'
INDISPONIVEL = 'indisponivel'

CALIBRADO = 'calibrado'
SEM_NATIVO = 'sem_nativo'
AMOSTRA_INSUFICIENTE = 'amostra_insuficiente'
FORA_DA_FAIXA = 'fora_da_faixa'

TREINO_MINIMO_ORIGEM = 2
ORIGENS_MINIMAS = 2
TOLERANCIA_SUBCOBERTURA = 0.05
CONFIANCA_COBERTURA = 0.95
_FOLGA_ARREDONDAMENTO = 1e-9

Limites = dict[float, tuple[np.ndarray, np.ndarray]]


def rotulo(nivel: float) -> str:
    """Nível como aparece nos nomes (`0.8` vira `80`)."""
    return f'{nivel * 100:g}'


@dataclass(frozen=True)
class ConfigIntervalos:
    niveis: tuple[float, ...]
    max_origens: int = 70

    def __post_init__(self):
        if not self.niveis or not all(0 < n < 1 for n in self.niveis):
            raise ValueError(f'níveis inválidos: {self.niveis}')
        if self.max_origens < 1:
            raise ValueError('max_origens deve ser >= 1')


def fracao_zeros(y) -> float:
    """Fração de períodos sem venda em `y` (só o treino)."""
    return float(np.mean(np.asarray(y, dtype=float) == 0))


def tem_piso_zero(nivel: float, fracao: float) -> bool:
    """Emenda D-009: zeros frequentes o bastante para a cauda do nível."""
    return fracao >= (1 - nivel) / 2 - _FOLGA_ARREDONDAMENTO


def normalizar(previsto, brutos: Limites, fracao: float = 0.0) -> Limites:
    """Trunca em zero, contém a previsão e aninha os níveis.

    `fracao` é a fração de zeros do treino: com `tem_piso_zero`, o
    inferior do nível é zero. Os ajustes só alargam. `nan` (método
    indisponível) se propaga.
    """
    previsto = np.clip(np.asarray(previsto, dtype=float), 0, None)
    inferior, superior = previsto, previsto
    saida = {}
    for nivel in sorted(brutos):
        baixo, alto = brutos[nivel]
        if tem_piso_zero(nivel, fracao):
            baixo = np.where(np.isnan(baixo), baixo, 0.0)
        inferior = np.minimum(np.clip(baixo, 0, None), inferior)
        superior = np.maximum(np.clip(alto, 0, None), superior)
        saida[nivel] = (inferior, superior)
    return saida


# --- mecanismo empírico ------------------------------------------------


@dataclass(frozen=True)
class Calibracao:
    """Como transformar uma previsão em limites (é salva com o modelo)."""

    metodo: str
    niveis: tuple[float, ...]
    horizonte: int
    deslocamentos: dict[float, tuple[float, float]]
    n_erros: int = 0
    n_origens: int = 0
    n_falhas: int = 0
    fracao_zeros: float = 0.0

    def limites(self, previsor: Previsor, previsto, horizonte: int) -> Limites:
        """Limites sem pós-processamento para os próximos `horizonte`."""
        if horizonte > self.horizonte:
            raise ValueError(
                f'horizonte {horizonte} acima do calibrado ({self.horizonte})'
            )
        if self.metodo == NATIVO:
            return previsor.intervalos_nativos(horizonte, self.niveis)
        previsto = np.clip(np.asarray(previsto, dtype=float), 0, None)
        return {
            n: (previsto + baixo, previsto + alto)
            for n, (baixo, alto) in self.deslocamentos.items()
        }


def nativa(niveis: tuple[float, ...], horizonte: int, y) -> Calibracao:
    """Calibração do nativo: guarda só os zeros de `y` (o treino)."""
    return Calibracao(
        NATIVO, niveis, horizonte, {}, fracao_zeros=fracao_zeros(y)
    )


def _erros_por_origem(
    fabrica: Callable[[], Previsor],
    y: np.ndarray,
    horizonte: int,
    max_origens: int,
) -> tuple[list[np.ndarray], int]:
    """Erros de 1 a `horizonte` passos, um vetor por origem, e as falhas."""
    ultima = len(y) - horizonte
    primeira = max(TREINO_MINIMO_ORIGEM, ultima - max_origens + 1)
    erros, falhas = [], 0
    for t in range(primeira, ultima + 1):
        try:
            previsto = np.asarray(
                fabrica().ajustar(y[:t]).prever(horizonte), dtype=float
            )
            if not np.isfinite(previsto).all():
                raise ValueError('previsão não finita')
        # O contrato não restringe a exceção de um previsor (a falha de
        # convergência do #11 é definida lá): origem que falha é pulada,
        # contada e registrada.
        except Exception as erro:  # noqa: BLE001
            logger.debug('origem {} falhou: {}', t, erro)
            falhas += 1
            continue
        erros.append(y[t : t + horizonte] - np.clip(previsto, 0, None))
    return erros, falhas


def minimo_de_erros(nivel: float) -> int:
    """Menor amostra em que os dois quantis corrigidos existem."""
    return ceil(2 / (1 - nivel) - _FOLGA_ARREDONDAMENTO) - 1


def _quantis(erros: np.ndarray, nivel: float) -> tuple[float, float]:
    ordenados = np.sort(erros)
    m = len(ordenados)
    k = floor((m + 1) * (1 - nivel) / 2 + _FOLGA_ARREDONDAMENTO)
    return float(ordenados[k - 1]), float(ordenados[m - k])


def _student(
    erros: np.ndarray, n_origens: int, nivel: float
) -> tuple[float, float]:
    media = float(np.mean(erros))
    multiplicador = stats.t.ppf(1 - (1 - nivel) / 2, n_origens - 1)
    meia = multiplicador * np.std(erros, ddof=1) * sqrt(1 + 1 / n_origens)
    return media - float(meia), media + float(meia)


def calibrar(
    fabrica: Callable[[], Previsor],
    y,
    horizonte: int,
    config: ConfigIntervalos,
) -> Calibracao:
    """Ajusta o mecanismo empírico só com `y`, para até `horizonte` passos.

    O método depende apenas do tamanho da amostra: quantis com erros
    suficientes; t de Student com poucos; indisponível com menos de 2
    origens válidas.
    """
    y = np.asarray(y, dtype=float)
    por_origem, falhas = _erros_por_origem(
        fabrica, y, horizonte, config.max_origens
    )
    n_origens = len(por_origem)
    erros = np.concatenate(por_origem) if por_origem else np.empty(0)
    m = len(erros)
    if m >= minimo_de_erros(max(config.niveis)):
        metodo = QUANTIL
        desloca = {n: _quantis(erros, n) for n in config.niveis}
    elif n_origens >= ORIGENS_MINIMAS:
        metodo = STUDENT
        desloca = {n: _student(erros, n_origens, n) for n in config.niveis}
    else:
        metodo = INDISPONIVEL
        nan = float('nan')
        desloca = dict.fromkeys(config.niveis, (nan, nan))
    return Calibracao(
        metodo,
        config.niveis,
        horizonte,
        desloca,
        m,
        n_origens,
        falhas,
        fracao_zeros(y),
    )


# --- intervalo nativo --------------------------------------------------


def tem_nativo(previsor: Previsor) -> bool:
    return callable(getattr(previsor, 'intervalos_nativos', None))


def limites_nativos(
    previsor: Previsor, horizonte: int, niveis: tuple[float, ...]
) -> Limites | None:
    """Limites do previsor, ou `None` se ele não os tem ou são inválidos."""
    if not tem_nativo(previsor):
        return None
    try:
        brutos = previsor.intervalos_nativos(horizonte, niveis)
        limites = {
            n: (
                np.asarray(brutos[n][0], dtype=float),
                np.asarray(brutos[n][1], dtype=float),
            )
            for n in niveis
        }
    except Exception as erro:  # noqa: BLE001
        logger.warning('intervalo nativo falhou: {}', erro)
        return None
    for baixo, alto in limites.values():
        validos = (
            baixo.shape == alto.shape == (horizonte,)
            and np.isfinite(baixo).all()
            and np.isfinite(alto).all()
            and (baixo <= alto).all()
        )
        if not validos:
            logger.warning('intervalo nativo inválido')
            return None
    return limites


# --- cobertura ---------------------------------------------------------


@dataclass(frozen=True)
class Cobertura:
    """`k` de `n` pontos dentro do intervalo, com o IC de Wilson."""

    k: int
    n: int

    @property
    def valor(self) -> float:
        return self.k / self.n if self.n else float('nan')

    @property
    def ic(self) -> tuple[float, float]:
        return wilson(self.k, self.n)


def wilson(
    k: int, n: int, confianca: float = CONFIANCA_COBERTURA
) -> tuple[float, float]:
    """IC de Wilson; supõe pontos independentes (aqui, é otimista)."""
    if n == 0:
        return float('nan'), float('nan')
    z = float(stats.norm.ppf(1 - (1 - confianca) / 2))
    p = k / n
    denominador = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / denominador
    margem = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominador
    # Nos extremos a conta exata dá 0 e 1; o arredondamento não pode mudar.
    baixo = 0.0 if k == 0 else centro - margem
    alto = 1.0 if k == n else centro + margem
    return baixo, alto


def contar(observado, inferior, superior) -> Cobertura:
    """Cobertura inclusiva nas pontas; limite `nan` fica fora da conta."""
    observado = np.asarray(observado, dtype=float)
    definidos = np.isfinite(inferior) & np.isfinite(superior)
    dentro = (observado >= inferior) & (observado <= superior)
    return Cobertura(int((dentro & definidos).sum()), int(definidos.sum()))


def decidir_nativo(
    coberturas: dict[float, Cobertura] | None,
) -> tuple[bool, str]:
    """Regra R1 a R4 do plano: o nativo precisa se mostrar calibrado."""
    if coberturas is None:
        return False, SEM_NATIVO
    maior = max(coberturas)
    n = coberturas[maior].n
    if n < ceil(1 / (1 - maior) - _FOLGA_ARREDONDAMENTO):
        return False, AMOSTRA_INSUFICIENTE
    for nivel, cobertura in coberturas.items():
        baixo, alto = cobertura.ic
        if not baixo <= nivel <= alto:
            return False, FORA_DA_FAIXA
        if cobertura.valor < nivel - TOLERANCIA_SUBCOBERTURA:
            return False, FORA_DA_FAIXA
    return True, CALIBRADO


@dataclass(frozen=True)
class IntervalosFold:
    """Limites de um fold, sempre do treino do fold, já normalizados."""

    empirico: Limites
    nativo: Limites | None
    calibracao: Calibracao


def intervalos_do_fold(
    fabrica: Callable[[], Previsor],
    ajustado: Previsor,
    treino: np.ndarray,
    previsto: np.ndarray,
    config: ConfigIntervalos,
) -> IntervalosFold:
    """Empírico e, se houver, nativo para o teste do fold.

    `ajustado` é o previsor do fold; `treino` é tudo o que o mecanismo vê.
    """
    horizonte = len(previsto)
    calibracao = calibrar(fabrica, treino, horizonte, config)
    brutos = limites_nativos(ajustado, horizonte, config.niveis)
    return IntervalosFold(
        normalizar(
            previsto,
            calibracao.limites(ajustado, previsto, horizonte),
            calibracao.fracao_zeros,
        ),
        None
        if brutos is None
        else normalizar(previsto, brutos, calibracao.fracao_zeros),
        calibracao,
    )


@dataclass(frozen=True)
class ResumoIntervalos:
    """Cobertura do backtest e a decisão do método."""

    usar_nativo: bool
    motivo: str
    empirico: dict[float, Cobertura]
    nativo: dict[float, Cobertura] | None
    por_fold: dict[float, tuple[Cobertura, ...]]
    amplitude: dict[float, float]
    sem_atipico: dict[float, Cobertura]
    metodos_fold: tuple[str, ...]

    @property
    def usada(self) -> dict[float, Cobertura]:
        return self.nativo if self.usar_nativo else self.empirico


def _total(parciais: Sequence[Cobertura]) -> Cobertura:
    return Cobertura(sum(c.k for c in parciais), sum(c.n for c in parciais))


def _por_nivel(
    limites: Sequence[Limites],
    observados: Sequence[np.ndarray],
    niveis: tuple[float, ...],
) -> dict[float, tuple[Cobertura, ...]]:
    return {
        n: tuple(
            contar(obs, *lim[n])
            for obs, lim in zip(observados, limites, strict=True)
        )
        for n in niveis
    }


def _totais(
    limites: Sequence[Limites],
    observados: Sequence[np.ndarray],
    niveis: tuple[float, ...],
) -> dict[float, Cobertura]:
    return {
        n: _total(c)
        for n, c in _por_nivel(limites, observados, niveis).items()
    }


def _amplitude(limites: Sequence[Limites], nivel: float) -> float:
    larguras = np.concatenate([
        lim[nivel][1] - lim[nivel][0] for lim in limites
    ])
    definidas = larguras[np.isfinite(larguras)]
    return float(definidas.mean()) if definidas.size else float('nan')


def resumir(
    folds: Sequence[IntervalosFold],
    observados: Sequence[np.ndarray],
    niveis: tuple[float, ...],
    manter: Sequence[np.ndarray] | None = None,
) -> ResumoIntervalos:
    """Coberturas de todos os folds e a escolha do método (R1 a R4).

    `manter` marca, por fold, os pontos da sensibilidade ao período atípico.
    """
    empiricos = [f.empirico for f in folds]
    nativos = [f.nativo for f in folds]
    cobertura_nativo = None
    if all(n is not None for n in nativos):
        cobertura_nativo = _totais(nativos, observados, niveis)
    usar_nativo, motivo = decidir_nativo(cobertura_nativo)
    usados = nativos if usar_nativo else empiricos
    sem_atipico = {}
    if manter is not None:
        recortes = [
            {n: (lim[n][0][m], lim[n][1][m]) for n in niveis}
            for lim, m in zip(usados, manter, strict=True)
        ]
        filtrados = [obs[m] for obs, m in zip(observados, manter, strict=True)]
        sem_atipico = _totais(recortes, filtrados, niveis)
    return ResumoIntervalos(
        usar_nativo,
        motivo,
        _totais(empiricos, observados, niveis),
        cobertura_nativo,
        _por_nivel(usados, observados, niveis),
        {n: _amplitude(usados, n) for n in niveis},
        sem_atipico,
        tuple(NATIVO if usar_nativo else f.calibracao.metodo for f in folds),
    )
