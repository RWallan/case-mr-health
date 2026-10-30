"""Explicação da recomendação em linguagem simples (#20).

A decisão é só da regra (#18); aqui só se explica o que ela decidiu. A
explicação vem de um LLM de qualquer provedor (litellm), sem ferramentas nem
acesso externo, a
partir de um contrato estruturado. A saída é validada por schema e toda
quantidade citada precisa estar na entrada. Sem chave, com falha do LLM ou
com saída inválida, vale o template determinístico com os mesmos números.
"""

import json
import re
from collections.abc import Callable
from datetime import date, timedelta
from typing import Literal

from loguru import logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from case_mr_health.config import Settings
from case_mr_health.recomendacao import (
    MINIMO_VARIACOES,
    SEMANAS_BASE,
    SEMANAS_PREVISTAS,
    Motivo,
    Resultado,
)

Origem = Literal['llm', 'template']
# Recebe a entrada e devolve o texto bruto do LLM (JSON com `texto`).
GeradorLLM = Callable[['EntradaExplicacao'], str]

TAMANHO_MAXIMO = 1200
NIVEIS = (80, 95)
TOLERANCIA = 1e-9
_NUMERO = re.compile(r'\d+(?:[.,]\d+)?')
_CERCA = re.compile(r'^```(?:json)?\s*|\s*```$')

_RESULTADOS = {
    'aumento_significativo': 'aumento significativo',
    'reducao_significativa': 'redução significativa',
    'estavel': 'estável',
    'insuficiente': 'insuficiente',
}
_MOTIVOS = {
    'sem_venda_recente': (
        'a venda média das últimas 4 semanas é zero, então a variação não '
        'pode ser calculada'
    ),
    'variacoes_insuficientes': (
        f'há menos de {MINIMO_VARIACOES} variações históricas do mesmo '
        'sentido para formar o limite'
    ),
}
_INSTRUCAO = (
    'Você explica, em português simples e em poucas frases, uma '
    'recomendação de estoque já decidida por uma regra determinística. '
    'Não decida nem altere o resultado. Use apenas os números do JSON '
    'recebido: nunca invente estoques, prazos, fornecedores ou quantidades. '
    'Fale em "pressão sobre o estoque" e nunca afirme ruptura. Cite os '
    'números que sustentam o resultado e as incertezas (poucas janelas '
    'históricas, intervalo de 80%). Responda somente com um JSON no formato '
    '{"texto": "..."}.'
)


class EntradaExplicacao(BaseModel):
    """Contrato de entrada: tudo o que a explicação pode citar."""

    model_config = ConfigDict(frozen=True)

    sku: str
    granularidade: Literal['semanal'] = 'semanal'
    nivel: Literal['rede'] = 'rede'
    primeira_semana_prevista: date
    vendas_4s: list[float] = Field(min_length=SEMANAS_BASE)
    previsao_2s: list[float] = Field(min_length=SEMANAS_PREVISTAS)
    # Intervalo de 80% de cada semana prevista, quando existir.
    limites_80: list[tuple[float, float]] = Field(default_factory=list)
    media_vendida_4s: float
    media_prevista_2s: float
    variacao: float | None
    limite_aplicado: float | None
    n_variacoes_positivas: int
    n_variacoes_negativas: int
    resultado: Resultado
    motivo: Motivo | None
    # Sem dado de estoque no projeto: só entra se alguém o informar.
    estoque: float | None = None
    confianca: float | None = None
    metricas: dict[str, float] = Field(default_factory=dict)

    @property
    def semanas_previstas(self) -> list[date]:
        return [
            self.primeira_semana_prevista + timedelta(weeks=i)
            for i in range(len(self.previsao_2s))
        ]


class SaidaLLM(BaseModel):
    """Schema da saída do LLM."""

    model_config = ConfigDict(extra='forbid')

    texto: str = Field(min_length=1, max_length=TAMANHO_MAXIMO)

    @field_validator('texto')
    @classmethod
    def sem_ruptura(cls, texto: str) -> str:
        if 'ruptura' in texto.lower():
            raise ValueError('o texto não pode afirmar ruptura')
        return texto


class Explicacao(BaseModel):
    texto: str
    origem: Origem


# --- números ---------------------------------------------------------------


def _formatar(valor: float, casas: int = 1) -> str:
    return f'{valor:.{casas}f}'.replace('.', ',')


def _quantidade(valor: float) -> str:
    """Inteiro sem casas; fracionário com uma casa."""
    if float(valor).is_integer():
        return f'{valor:.0f}'
    return _formatar(valor)


def _pct(valor: float) -> str:
    return _formatar(abs(valor) * 100) + '%'


def _data(dia: date) -> str:
    return dia.strftime('%d/%m/%Y')


def _numeros_permitidos(entrada: EntradaExplicacao) -> list[float]:
    permitidos = [
        SEMANAS_BASE,
        SEMANAS_PREVISTAS,
        MINIMO_VARIACOES,
        *NIVEIS,
        *entrada.vendas_4s,
        *entrada.previsao_2s,
        entrada.media_vendida_4s,
        entrada.media_prevista_2s,
        entrada.n_variacoes_positivas,
        entrada.n_variacoes_negativas,
        *(x for par in entrada.limites_80 for x in par),
        *entrada.metricas.values(),
    ]
    for opcional in (entrada.estoque, entrada.confianca):
        if opcional is not None:
            permitidos.append(opcional)
    for fracao in (entrada.variacao, entrada.limite_aplicado):
        if fracao is not None:
            permitidos += [abs(fracao) * 100, abs(fracao)]
    for dia in entrada.semanas_previstas:
        permitidos += [dia.day, dia.month, dia.year]
    return [float(x) for x in permitidos]


def numeros_fora_da_entrada(
    texto: str, entrada: EntradaExplicacao
) -> list[float]:
    """Números do texto sem correspondente na entrada.

    A comparação respeita as casas escritas: `47` casa com 47,06 e `47,1`
    também, mas `48` não. O dígito de sku (`item A`) não tem número.
    """
    permitidos = _numeros_permitidos(entrada)
    fora = []
    for bruto in _NUMERO.findall(texto.replace('Q3', '')):
        casas = len(bruto.split(',')[1]) if ',' in bruto else 0
        if '.' in bruto:
            casas = len(bruto.split('.')[1])
        numero = float(bruto.replace(',', '.'))
        if not any(
            abs(round(a, casas) - numero) < TOLERANCIA for a in permitidos
        ):
            fora.append(numero)
    return fora


# --- template --------------------------------------------------------------


def montar_template(entrada: EntradaExplicacao) -> str:
    """Texto determinístico com os mesmos números da entrada."""
    semanas = ' e '.join(_data(d) for d in entrada.semanas_previstas)
    vendas = ', '.join(_quantidade(v) for v in entrada.vendas_4s)
    previsoes = ' e '.join(_quantidade(p) for p in entrada.previsao_2s)
    partes = [
        f'{entrada.sku} (rede, semanal): resultado da regra, '
        f'{_RESULTADOS[entrada.resultado]}.',
        f'Nas últimas {SEMANAS_BASE} semanas foram vendidas {vendas} '
        f'unidades (média {_formatar(entrada.media_vendida_4s)}).',
        f'Para as semanas iniciadas em {semanas} a previsão é {previsoes} '
        f'(média {_formatar(entrada.media_prevista_2s)}).',
    ]
    if entrada.resultado == 'insuficiente':
        partes.append(
            f'Sem base estatística: {_MOTIVOS[entrada.motivo]}. Não há '
            'indicação de pressão sobre o estoque.'
        )
    else:
        partes.append(_frase_variacao(entrada))
    if entrada.limites_80:
        faixas = ' e '.join(
            f'{_quantidade(i)} a {_quantidade(s)}'
            for i, s in entrada.limites_80
        )
        partes.append(f'Faixa de {NIVEIS[0]}% da previsão: {faixas}.')
    if entrada.estoque is not None:
        partes.append(f'O estoque atual é de {_quantidade(entrada.estoque)}.')
    partes.append(
        'Incerteza: poucas janelas históricas sustentam o limite '
        f'({entrada.n_variacoes_positivas} variações positivas e '
        f'{entrada.n_variacoes_negativas} negativas); a recomendação tem '
        'baixa confiabilidade estatística.'
    )
    return ' '.join(partes)


def _frase_variacao(entrada: EntradaExplicacao) -> str:
    diferenca = _pct(entrada.variacao)
    limite = _pct(entrada.limite_aplicado or 0)
    if entrada.resultado == 'estavel':
        return (
            f'A previsão difere {diferenca} da venda recente, sem passar '
            'do limite histórico (Q3). Sem pressão significativa sobre o '
            'estoque.'
        )
    if entrada.resultado == 'aumento_significativo':
        return (
            f'A previsão supera a venda recente em {diferenca}, acima do '
            f'limite histórico (Q3) de {limite}. Indica pressão de alta '
            'sobre o estoque.'
        )
    return (
        f'A previsão fica {diferenca} abaixo da venda recente, além do '
        f'limite histórico (Q3) de {limite}. Indica pressão de baixa '
        'sobre o estoque.'
    )


# --- LLM -------------------------------------------------------------------


def criar_gerador(
    modelo: str,
    api_key: str,
    timeout_s: float,
    max_tokens: int,
) -> GeradorLLM:
    """Gerador agnóstico ao provedor (litellm).

    `modelo` segue a notação do litellm (`anthropic/claude-sonnet-5-5`,
    `openai/gpt-4o`, `gemini/gemini-2.0-flash`...). A chave é usada só na
    chamada e nunca é registrada em log.
    """

    def gerar(entrada: EntradaExplicacao) -> str:
        import litellm  # noqa: PLC0415

        resposta = litellm.completion(
            model=modelo,
            api_key=api_key,
            max_tokens=max_tokens,
            timeout=timeout_s,
            num_retries=1,
            messages=[
                {'role': 'system', 'content': _INSTRUCAO},
                {'role': 'user', 'content': entrada.model_dump_json()},
            ],
        )
        bruto = resposta.choices[0].message.content or ''
        if api_key in bruto:
            # Um LLM que devolve a chave não a leva à resposta nem ao log.
            raise ValueError('a saída do LLM continha a chave')
        return bruto

    return gerar


def criar_gerador_padrao(cfg: Settings) -> GeradorLLM | None:
    """Gerador da configuração do servidor, ou `None` sem chave."""
    if cfg.llm_api_key is None:
        return None
    return criar_gerador(
        cfg.llm_modelo,
        cfg.llm_api_key.get_secret_value(),
        cfg.llm_timeout_s,
        cfg.llm_max_tokens,
    )


def gerador_do_usuario(
    cfg: Settings, modelo: str | None, api_key: str | None
) -> GeradorLLM | None:
    """Gerador com a chave informada pelo usuário na requisição.

    `None` quando a chave não veio; o modelo cai no da configuração.
    """
    if not api_key:
        return None
    return criar_gerador(
        modelo or cfg.llm_modelo,
        api_key,
        cfg.llm_timeout_s,
        cfg.llm_max_tokens,
    )


def _validar(bruto: str, entrada: EntradaExplicacao) -> str:
    """Texto aprovado ou `ValueError`/`ValidationError`."""
    limpo = _CERCA.sub('', bruto.strip())
    saida = SaidaLLM.model_validate(json.loads(limpo))
    fora = numeros_fora_da_entrada(saida.texto, entrada)
    if fora:
        raise ValueError(f'números fora da entrada: {fora}')
    return saida.texto


def explicar(
    entrada: EntradaExplicacao, gerador: GeradorLLM | None
) -> Explicacao:
    """LLM validado; template em qualquer outro caso. Nunca levanta erro."""
    if gerador is not None:
        try:
            bruto = gerador(entrada)
        except Exception as erro:  # noqa: BLE001
            # Só o tipo: a mensagem de uma exceção do provedor pode trazer
            # a chave (#44).
            logger.warning('Falha do LLM: {}', type(erro).__name__)
        else:
            try:
                return Explicacao(texto=_validar(bruto, entrada), origem='llm')
            except (ValueError, ValidationError) as erro:
                logger.warning('Saída do LLM rejeitada: {}', erro)
    return Explicacao(texto=montar_template(entrada), origem='template')
