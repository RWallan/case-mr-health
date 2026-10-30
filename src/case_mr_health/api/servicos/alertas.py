"""E-mail de alerta mockado (#21).

Monta o conteúdo que seria enviado e o devolve. Não há envio: nenhuma
conexão SMTP é aberta. A previsão e a recomendação seguem o #19 (origem
fixa, 2 semanas), e a chamada é gravada uma única vez no histórico.
"""

from datetime import timedelta

from case_mr_health.api.erros import SkuInexistente
from case_mr_health.api.historico import Historico
from case_mr_health.api.modelos import CatalogoModelos
from case_mr_health.api.schemas.alertas import (
    PedidoAlertaEmail,
    RecomendacaoAlerta,
    RespostaAlertaEmail,
)
from case_mr_health.api.schemas.recomendacao import AVISO
from case_mr_health.api.servicos import consultas, predicao
from case_mr_health.api.servicos.recomendacao import montar_texto
from case_mr_health.config import Settings
from case_mr_health.particoes import DIAS_POR_PERIODO
from case_mr_health.recomendacao import SEMANAS_PREVISTAS, recomendar
from case_mr_health.treino import normalizar_sku

AVISO_ENVIO = (
    'Envio simulado: nada foi enviado para {email}. Esta resposta mostra '
    'apenas o conteúdo que o alerta teria.'
)


def montar_alerta(
    pedido: PedidoAlertaEmail,
    modelos: CatalogoModelos,
    historico: Historico,
    cfg: Settings,
) -> RespostaAlertaEmail:
    try:
        sku = normalizar_sku(pedido.sku)
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
    prevista = predicao.registrar_previsao(
        modelo,
        ultima_semana,
        previsto,
        historico,
        cfg,
        recomendacao=regra.resultado,
    )
    return RespostaAlertaEmail(
        id_requisicao=prevista.id_requisicao,
        aviso_envio=AVISO_ENVIO.format(email=pedido.email),
        destinatario=pedido.email,
        assunto=f'Alerta de demanda: {sku} (semanal)',
        sku=sku,
        periodos=prevista.periodos,
        valor_total_previsto=sum(p.valor_previsto for p in prevista.periodos),
        recomendacao=RecomendacaoAlerta(
            resultado=regra.resultado,
            motivo=regra.motivo,
            variacao=regra.variacao,
            limite_aplicado=regra.limite_aplicado,
            media_vendida_4s=regra.media_vendida_4s,
            media_prevista_2s=regra.media_prevista_2s,
            n_variacoes_positivas=regra.n_variacoes_positivas,
            n_variacoes_negativas=regra.n_variacoes_negativas,
            texto=montar_texto(regra),
            aviso=AVISO,
        ),
        versao_modelo=modelo.versao,
        hash_artefato=modelo.hash_artefato,
        origem_modelo=modelo.origem,
    )
