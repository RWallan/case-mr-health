"""Tabela de candidatos de algoritmo por série (#6).

Nada aqui treina ou ajusta modelos. A tabela decide quem entra no backtest
(#7 em diante), com as premissas de cada candidato, a base da decisão
(evidência do #5, hipótese, decisão do usuário ou aritmética) e o espaço de
hiperparâmetros. As regras estão em `docs/analysis/plano-candidatos.md`
(congelado antes de qualquer resultado de método).
"""

from dataclasses import dataclass
from itertools import product
from math import prod

from case_mr_health.particoes import GRANULARIDADES

SKUS = ('item A', 'item B', 'item C', 'item D')
MAX_COMBINACOES = 4
PERIODO_SEMANAL_DIARIA = 7

EVIDENCIA = 'evidencia'
HIPOTESE = 'hipotese'
DECISAO_USUARIO = 'decisao_usuario'
ARITMETICA = 'aritmetica'
REGRA = 'regra'

ATENDIDA = 'atendida'
NAO_ATENDIDA = 'nao_atendida'
INCONCLUSIVA = 'inconclusiva'
NAO_TESTAVEL = 'nao_testavel'


@dataclass(frozen=True)
class EvidenciaSerie:
    """Resultado do #5 (aprovado pelo usuário) usado pela tabela."""

    classe: str  # classificação de Syntetos, Boylan e Croston
    estacionaria: str  # 'sim' ou NAO_TESTAVEL
    autocorrelacao_fraca: bool | None  # Ljung-Box não rejeita ruído
    sazonalidade: str  # 'confirmada', INCONCLUSIVA ou NAO_TESTAVEL


# Fonte: notebooks/02_eda_series.ipynb e registro-fase1.md, seção 3.4.
_DIARIA = {
    'item A': 'inconclusiva',
    'item B': 'confirmada',
    'item C': 'confirmada',
    'item D': 'inconclusiva',
}
EVIDENCIAS: dict[tuple[str, str], EvidenciaSerie] = {
    **{
        (sku, 'diaria'): EvidenciaSerie('intermitente', 'sim', True, saz)
        for sku, saz in _DIARIA.items()
    },
    **{
        (sku, 'semanal'): EvidenciaSerie(
            'suave', NAO_TESTAVEL, None, NAO_TESTAVEL
        )
        for sku in SKUS
    },
}


@dataclass(frozen=True)
class Premissa:
    texto: str
    situacao: str
    base: str
    estrutural: bool = True


@dataclass(frozen=True)
class Candidato:
    algoritmo: str
    familia: str
    papel: str  # 'baseline' ou 'candidato'
    entra: bool
    base: str
    motivo: str
    premissas: tuple[Premissa, ...] = ()
    espaco: dict[str, tuple] | None = None
    observacao: str = ''

    @property
    def n_combinacoes(self) -> int:
        if not self.entra or not self.espaco:
            return 1 if self.entra else 0
        return prod(len(v) for v in self.espaco.values())

    def combinacoes(self) -> list[dict]:
        """Produto cartesiano do espaço (uma combinação vazia se não há)."""
        if not self.entra:
            return []
        if not self.espaco:
            return [{}]
        chaves = list(self.espaco)
        return [
            dict(zip(chaves, valores, strict=True))
            for valores in product(*self.espaco.values())
        ]


def _base_sazonal(ev: EvidenciaSerie) -> str:
    return EVIDENCIA if ev.sazonalidade == 'confirmada' else HIPOTESE


def _premissa_sazonal(ev: EvidenciaSerie) -> Premissa:
    situacao = {
        'confirmada': ATENDIDA,
        INCONCLUSIVA: INCONCLUSIVA,
        NAO_TESTAVEL: NAO_TESTAVEL,
    }[ev.sazonalidade]
    base = EVIDENCIA if ev.sazonalidade == 'confirmada' else HIPOTESE
    return Premissa(
        'Sazonalidade por dia da semana (período 7)', situacao, base
    )


def _premissa_nivel(ev: EvidenciaSerie) -> Premissa:
    if ev.estacionaria == 'sim':
        return Premissa(
            'Nível aproximadamente constante (estacionária em nível)',
            ATENDIDA,
            EVIDENCIA,
            estrutural=False,
        )
    return Premissa(
        'Nível aproximadamente constante (estacionária em nível)',
        NAO_TESTAVEL,
        HIPOTESE,
        estrutural=False,
    )


def _baselines(ev: EvidenciaSerie, diaria: bool) -> list[Candidato]:
    lista = [
        Candidato(
            'naive',
            'baseline',
            'baseline',
            True,
            REGRA,
            'Baseline obrigatório (ADR 0003): último valor observado.',
            (
                Premissa(
                    'O último período é bom guia do próximo',
                    NAO_TESTAVEL,
                    HIPOTESE,
                    estrutural=False,
                ),
            ),
            observacao=(
                'Na diária intermitente prevê zero depois de um dia sem '
                'venda; serve de piso de comparação.'
                if diaria
                else ''
            ),
        ),
        Candidato(
            'media_historica',
            'baseline',
            'baseline',
            True,
            REGRA,
            'Baseline obrigatório (ADR 0003): média expansiva do treino.',
            (_premissa_nivel(ev),),
        ),
    ]
    if diaria:
        lista.append(
            Candidato(
                'naive_sazonal',
                'baseline',
                'baseline',
                True,
                _base_sazonal(ev),
                'Repete o mesmo dia da semana anterior (lag 7). '
                + (
                    'Sazonalidade confirmada por teste formal.'
                    if ev.sazonalidade == 'confirmada'
                    else 'Teste de sazonalidade inconclusivo (baixo '
                    'poder); entra como hipótese por decisão do usuário.'
                ),
                (_premissa_sazonal(ev),),
                {'periodo': (PERIODO_SEMANAL_DIARIA,)},
            )
        )
    else:
        lista.append(
            Candidato(
                'naive_sazonal',
                'baseline',
                'baseline',
                False,
                ARITMETICA,
                'Sem sazonalidade testável em 10 semanas; ciclo de 4 ou '
                '52 semanas não cabe nos dados.',
            )
        )
    return lista


def _ets_arima(ev: EvidenciaSerie, diaria: bool) -> list[Candidato]:
    nivel = _premissa_nivel(ev)
    zeros = Premissa(
        'Valores contínuos, erro simétrico (zeros e contagens violam '
        'em parte; previsões são truncadas em zero)',
        NAO_ATENDIDA if diaria else INCONCLUSIVA,
        HIPOTESE,
        estrutural=False,
    )
    ruido = Premissa(
        'Dependência temporal a modelar (autocorrelação)',
        (NAO_ATENDIDA if ev.autocorrelacao_fraca else NAO_TESTAVEL),
        EVIDENCIA if ev.autocorrelacao_fraca else HIPOTESE,
        estrutural=False,
    )
    ses = Candidato(
        'ets_ses',
        'ets',
        'candidato',
        True,
        REGRA,
        'ETS sem tendência nem sazonalidade (ANN), entre o naive e a média.',
        (nivel, zeros),
        {'alfa': ('estimado',)},
    )
    if diaria:
        return [
            ses,
            Candidato(
                'ets_holt_winters_aditivo',
                'ets',
                'candidato',
                True,
                _base_sazonal(ev),
                'Nível e sazonalidade aditivos de período 7. Sem '
                'componente multiplicativo (zeros) e sem tendência '
                '(estacionária em nível).',
                (_premissa_sazonal(ev), nivel, zeros),
                {'periodo': (7,), 'tendencia': ('nenhuma',)},
            ),
            Candidato(
                'arima',
                'arima',
                'candidato',
                False,
                DECISAO_USUARIO,
                'Corte de 2026-10-30, decisão do usuário (emenda a D-004): '
                'autocorrelação fraca nas 4 séries (Ljung-Box não rejeita '
                'ruído), logo pouco a modelar e tende a repetir a média.',
                (nivel, ruido),
                {'ordem': ((1, 0, 0), (0, 0, 1), (1, 0, 1))},
                'Com constante.',
            ),
            Candidato(
                'sarima',
                'arima',
                'candidato',
                True,
                _base_sazonal(ev),
                'ARIMA com termo sazonal AR(1) de período 7. O sazonal '
                '(0,0,0,7) coincide com o ARIMA sem sazonal e não é '
                'repetido. Sem ordens não sazonais desde o corte de '
                '2026-10-30 (decisão do usuário; emenda a D-004).',
                (_premissa_sazonal(ev), nivel, ruido),
                {
                    'ordem': ((0, 0, 0),),
                    'ordem_sazonal': ((1, 0, 0, 7),),
                },
                'Com constante.',
            ),
        ]
    return [
        ses,
        Candidato(
            'ets_holt_amortecido',
            'ets',
            'candidato',
            False,
            DECISAO_USUARIO,
            'Corte de 2026-10-30, decisão do usuário (emenda a D-004): '
            '5 parâmetros mais a variância em 6 a 10 pontos; razão de '
            'parâmetros por observação não atendida em 20 de 20 ajustes.',
            (
                Premissa(
                    'Possível tendência amortecida',
                    NAO_TESTAVEL,
                    HIPOTESE,
                    estrutural=False,
                ),
                zeros,
            ),
            {'phi': ('estimado em [0,8; 0,98]',)},
        ),
        Candidato(
            'arima',
            'arima',
            'candidato',
            False,
            DECISAO_USUARIO,
            'Corte de 2026-10-30, decisão do usuário (emenda a D-004): '
            'reverte a inclusão anterior. Base fraca: estacionariedade e '
            'autocorrelação semanais não são testáveis (n = 10 < 30); '
            '(0,1,1) é próximo do SES.',
            (
                Premissa(
                    'Estacionariedade (escolha de d)',
                    NAO_TESTAVEL,
                    HIPOTESE,
                ),
                Premissa(
                    'Dependência temporal a modelar',
                    NAO_TESTAVEL,
                    HIPOTESE,
                    estrutural=False,
                ),
            ),
            {'ordem': ((1, 0, 0), (0, 1, 1))},
            '(1,0,0) com constante; (0,1,1) sem constante. (0,1,1) é '
            'próximo do SES. Item C: variante opcional com variável de '
            'intervenção na semana 07-19.',
        ),
        Candidato(
            'sarima',
            'arima',
            'candidato',
            False,
            ARITMETICA,
            'Ciclo sazonal de 4 ou 52 semanas não cabe em 10 pontos. '
            'Exclusão sobre o universo do ADR 0003, sinalizada.',
        ),
    ]


def _intermitentes(ev: EvidenciaSerie, diaria: bool) -> list[Candidato]:
    nomes = (
        ('croston', 'Croston (1972): tamanho ÷ intervalo.'),
        ('sba', 'Croston com correção de viés (Syntetos–Boylan).'),
        ('tsb', 'Probabilidade de venda atualizada também nos zeros.'),
    )
    if not diaria:
        return [
            Candidato(
                nome,
                'intermitente',
                'candidato',
                False,
                EVIDENCIA,
                f'{descricao} Fora: série suave (ADI = 1, 0 zeros em 10 '
                'semanas); sem intermitência o método não tem razão de '
                'existir.',
            )
            for nome, descricao in nomes
        ]
    saz = Premissa(
        'Sem sazonalidade nem dia da semana (o método ignora)',
        NAO_ATENDIDA if ev.sazonalidade == 'confirmada' else INCONCLUSIVA,
        EVIDENCIA if ev.sazonalidade == 'confirmada' else HIPOTESE,
        estrutural=False,
    )
    inter = Premissa('Demanda intermitente (ADI >= 1,32)', ATENDIDA, EVIDENCIA)
    candidatos = []
    for nome, descricao in nomes:
        espaco = (
            {'alfa_beta': (0.1, 0.2, 0.3)}
            if nome == 'tsb'
            else {'alfa': (0.1, 0.2, 0.3)}
        )
        candidatos.append(
            Candidato(
                nome,
                'intermitente',
                'candidato',
                True,
                EVIDENCIA,
                f'{descricao} Entra: a série é intermitente.',
                (inter, saz),
                espaco,
                'Implementação própria (ADR 0003). Previsão constante, '
                'sem dia da semana.'
                + (' α = β no TSB.' if nome == 'tsb' else ''),
            )
        )
    return candidatos


def _prophet(ev: EvidenciaSerie, diaria: bool) -> list[Candidato]:
    if not diaria:
        return [
            Candidato(
                'prophet',
                'prophet',
                'candidato',
                False,
                DECISAO_USUARIO,
                'Fora da semanal por decisão do usuário (10 pontos, sem '
                'sazonalidade possível).',
            )
        ]
    return [
        Candidato(
            'prophet',
            'prophet',
            'candidato',
            False,
            DECISAO_USUARIO,
            'Corte de 2026-10-30, decisão do usuário (emenda a D-004): '
            'reverte a inclusão anterior. Com cerca de 80 dias, só a '
            'sazonalidade semanal é utilizável, o que o torna redundante '
            'com Holt-Winters e SARIMA.',
            (_premissa_sazonal(ev),),
            {'ordem_fourier': (2, 3), 'escala_sazonalidade': (1.0, 10.0)},
            'prophet 1.5.0 instala e ajusta no Python 3.14 (#5).',
        )
    ]


def candidatos(sku: str, granularidade: str) -> tuple[Candidato, ...]:
    """Candidatos de uma série, incluindo os excluídos e o porquê."""
    if granularidade not in GRANULARIDADES:
        raise ValueError(f'granularidade desconhecida: {granularidade}')
    if sku not in SKUS:
        raise ValueError(f'SKU desconhecido: {sku}')
    ev = EVIDENCIAS[sku, granularidade]
    diaria = granularidade == 'diaria'
    return tuple(
        _baselines(ev, diaria)
        + _ets_arima(ev, diaria)
        + _intermitentes(ev, diaria)
        + _prophet(ev, diaria)
    )


def tabela() -> list[dict]:
    """Tabela das 8 séries em linhas planas, consumível pelo treino."""
    linhas = []
    for sku, gran in product(SKUS, GRANULARIDADES):
        for c in candidatos(sku, gran):
            linhas.append({
                'sku': sku,
                'granularidade': gran,
                'algoritmo': c.algoritmo,
                'familia': c.familia,
                'papel': c.papel,
                'entra': c.entra,
                'base': c.base,
                'motivo': c.motivo,
                'premissas': [
                    f'{p.texto}: {p.situacao} ({p.base})' for p in c.premissas
                ],
                'espaco': c.espaco or {},
                'n_combinacoes': c.n_combinacoes,
                'observacao': c.observacao,
            })
    return linhas
