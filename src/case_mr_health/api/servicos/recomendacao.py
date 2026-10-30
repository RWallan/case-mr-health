"""Recomendação de um SKU a partir do modelo semanal (#19).

A origem é fixa, como na predição (#14): as 4 últimas semanas são as
completas do desenvolvimento e as 2 próximas são os passos 1 e 2 do modelo.
A chamada é gravada no histórico como as predições. Só lê o banco de
desenvolvimento; o OOT não é aberto.
"""

from datetime import date, timedelta
from math import isnan

import pandas as pd

from case_mr_health.api.erros import SkuInexistente
from case_mr_health.api.historico import Historico
from case_mr_health.api.modelos import CatalogoModelos
from case_mr_health.api.schemas.recomendacao import (
    AVISO,
    ExplicacaoResposta,
    RespostaRecomendacao,
)
from case_mr_health.api.servicos import consultas, predicao
from case_mr_health.config import Settings
from case_mr_health.explicacao import (
    EntradaExplicacao,
    GeradorLLM,
    explicar,
)
from case_mr_health.particoes import DIAS_POR_PERIODO
from case_mr_health.recomendacao import (
    SEMANAS_BASE,
    SEMANAS_PREVISTAS,
    Recomendacao,
    recomendar,
)
from case_mr_health.treino import normalizar_sku

_MOTIVOS = {
    'sem_venda_recente': (
        'a venda média das últimas 4 semanas é zero, então a variação não '
        'pode ser calculada'
    ),
    'variacoes_insuficientes': (
        'há menos de 3 variações históricas do mesmo sentido para formar '
        'o limite'
    ),
}


def _pct(valor: float) -> str:
    return f'{valor * 100:.1f}'.replace('.', ',')


def _num(valor: float) -> str:
    return f'{valor:.1f}'.replace('.', ',')


def montar_texto(r: Recomendacao) -> str:
    """Texto fixo por resultado; só a regra decide, sem modelo de linguagem."""
    if r.resultado == 'insuficiente':
        return (
            f'Insuficiente: {_MOTIVOS[r.motivo]}. Sem base estatística para '
            'indicar pressão sobre o estoque.'
        )
    previsto = (
        f'a demanda média prevista para as próximas {SEMANAS_PREVISTAS} '
        f'semanas ({_num(r.media_prevista_2s)})'
    )
    vendido = (
        f'a venda média das últimas {SEMANAS_BASE} semanas '
        f'({_num(r.media_vendida_4s)})'
    )
    diferenca = _pct(abs(r.variacao))
    if r.resultado == 'estavel':
        return (
            f'Estável: {previsto} difere {diferenca}% d{vendido}, sem '
            'passar do limite histórico. Sem pressão significativa sobre o '
            'estoque.'
        )
    limite = _pct(r.limite_aplicado)
    if r.resultado == 'aumento_significativo':
        return (
            f'Aumento significativo: {previsto} supera em {diferenca}% '
            f'{vendido}, acima do limite histórico de {limite}%. Indica '
            'pressão de alta sobre o estoque.'
        )
    return (
        f'Redução significativa: {previsto} fica {diferenca}% abaixo '
        f'd{vendido}, além do limite histórico de {limite}%. Indica '
        'pressão de baixa sobre o estoque.'
    )


def _entrada_explicacao(
    sku: str,
    ultima_semana: date,
    vendas: list[float],
    previsto: pd.DataFrame,
    regra: Recomendacao,
) -> EntradaExplicacao:
    """Contrato do LLM: só o que a regra e o modelo já produziram."""
    limites = list(
        zip(
            previsto['inferior_80'].tolist(),
            previsto['superior_80'].tolist(),
            strict=True,
        )
    )
    sem_intervalo = any(isnan(x) for par in limites for x in par)
    return EntradaExplicacao(
        sku=sku,
        primeira_semana_prevista=ultima_semana
        + timedelta(days=DIAS_POR_PERIODO['semanal']),
        vendas_4s=vendas[-SEMANAS_BASE:],
        previsao_2s=previsto['previsao'].tolist(),
        limites_80=[] if sem_intervalo else limites,
        media_vendida_4s=regra.media_vendida_4s,
        media_prevista_2s=regra.media_prevista_2s,
        variacao=regra.variacao,
        limite_aplicado=regra.limite_aplicado,
        n_variacoes_positivas=regra.n_variacoes_positivas,
        n_variacoes_negativas=regra.n_variacoes_negativas,
        resultado=regra.resultado,
        motivo=regra.motivo,
    )


def recomendar_sku(
    sku: str,
    modelos: CatalogoModelos,
    historico: Historico,
    cfg: Settings,
    gerador_llm: GeradorLLM | None = None,
) -> RespostaRecomendacao:
    try:
        sku = normalizar_sku(sku)
    except ValueError as erro:
        raise SkuInexistente(str(erro), campo='sku') from erro
    modelo = modelos.obter(sku, 'semanal')
    ultima_semana = modelo.desenvolvimento_fim - timedelta(
        days=DIAS_POR_PERIODO['semanal'] - 1
    )
    vendas = [
        ponto.quantidade
        for ponto in consultas.carregar_serie(cfg, sku, 'semanal')
        if ponto.data <= ultima_semana
    ]
    previsto = modelo.prever(SEMANAS_PREVISTAS)
    regra = recomendar(vendas, previsto['previsao'].tolist())
    registrada = predicao.registrar_previsao(
        modelo,
        ultima_semana,
        previsto,
        historico,
        cfg,
        recomendacao=regra.resultado,
    )
    explicacao = explicar(
        _entrada_explicacao(sku, ultima_semana, vendas, previsto, regra),
        gerador_llm,
    )
    return RespostaRecomendacao(
        id_requisicao=registrada.id_requisicao,
        sku=sku,
        resultado=regra.resultado,
        motivo=regra.motivo,
        variacao=regra.variacao,
        limite_aplicado=regra.limite_aplicado,
        media_vendida_4s=regra.media_vendida_4s,
        media_prevista_2s=regra.media_prevista_2s,
        n_variacoes_positivas=regra.n_variacoes_positivas,
        n_variacoes_negativas=regra.n_variacoes_negativas,
        texto=montar_texto(regra),
        explicacao=ExplicacaoResposta(**explicacao.model_dump()),
        aviso=AVISO,
        versao_modelo=modelo.versao,
        hash_artefato=modelo.hash_artefato,
        origem_modelo=modelo.origem,
    )
