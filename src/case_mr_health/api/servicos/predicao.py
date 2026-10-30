"""Regra da predição individual (#14).

A origem da previsão é fixa: o modelo foi ajustado até
`desenvolvimento_fim` e só prevê os períodos seguintes a ele. A data de
referência é o último período conhecido pelo solicitante (ausente, o fim do
treino do modelo servido, ADR 0013), e os alvos são os
`horizonte` períodos depois dela. Logo, o modelo prevê
`passo_inicial + horizonte` períodos, e só os últimos são servidos.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from math import isnan
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from case_mr_health.api.erros import (
    DataReferenciaInvalida,
    HorizonteAcimaDoLimite,
    SkuInexistente,
)
from case_mr_health.api.historico import Historico, LinhaHistorico
from case_mr_health.api.modelos import CatalogoModelos, ModeloServido
from case_mr_health.api.schemas.predicao import (
    PedidoPredicao,
    PeriodoPrevisto,
    RespostaPredicao,
)
from case_mr_health.config import Settings
from case_mr_health.particoes import DIAS_POR_PERIODO
from case_mr_health.treino import horizonte_maximo, normalizar_sku

_UNIDADE = {'diaria': 'dias', 'semanal': 'semanas'}


def _justificativa(limite: int, granularidade: str) -> str:
    return (
        f'o máximo validado empiricamente é de {limite} '
        f'{_UNIDADE[granularidade]} depois do fim do treino (tamanho do '
        'período OOT); além disso, o horizonte não tem validação'
    )


def normalizar_referencia(referencia: date, granularidade: str) -> date:
    """Na semanal, a segunda-feira da semana (Semana, no glossário)."""
    if granularidade == 'semanal':
        return referencia - timedelta(days=referencia.weekday())
    return referencia


def passo_inicial(
    referencia: date, desenvolvimento_fim: date, granularidade: str
) -> int:
    """Períodos entre o último do treino e a referência já normalizada.

    `desenvolvimento_fim` é o último dia do período: domingo, na semanal.
    """
    dias = DIAS_POR_PERIODO[granularidade]
    ultimo_periodo = desenvolvimento_fim - timedelta(days=dias - 1)
    return (referencia - ultimo_periodo).days // dias


@dataclass(frozen=True)
class Plano:
    """Pedido já validado: o modelo certo e os passos a servir."""

    modelo: ModeloServido
    referencia: date
    passo: int
    horizonte: int


def planejar(
    pedido: PedidoPredicao, modelos: CatalogoModelos, cfg: Settings
) -> Plano:
    """Todas as validações da predição, sem prever nem gravar nada."""
    granularidade, horizonte = pedido.granularidade, pedido.horizonte
    try:
        sku = normalizar_sku(pedido.sku)
    except ValueError as erro:
        raise SkuInexistente(str(erro), campo='sku') from erro
    limite = horizonte_maximo(cfg, granularidade)
    if horizonte > limite:
        raise HorizonteAcimaDoLimite(
            f'Horizonte {horizonte} acima do limite: '
            f'{_justificativa(limite, granularidade)}.',
            campo='horizonte',
        )
    modelo = modelos.obter(sku, granularidade)
    referencia = normalizar_referencia(
        pedido.data_referencia or modelo.desenvolvimento_fim, granularidade
    )
    passo = passo_inicial(
        referencia, modelo.desenvolvimento_fim, granularidade
    )
    if passo < 0:
        raise DataReferenciaInvalida(
            f'Data de referência {referencia} anterior ao fim do treino do '
            f'modelo ({modelo.desenvolvimento_fim}): o modelo só prevê '
            'períodos posteriores ao treino.',
            campo='data_referencia',
        )
    if passo + horizonte > limite:
        raise HorizonteAcimaDoLimite(
            f'A data de referência {referencia} e o horizonte {horizonte} '
            f'pedem o passo {passo + horizonte} a partir do fim do treino '
            f'({modelo.desenvolvimento_fim}): '
            f'{_justificativa(limite, granularidade)}.',
            campo='horizonte',
        )
    return Plano(modelo, referencia, passo, horizonte)


def executar(
    plano: Plano, historico: Historico, cfg: Settings
) -> RespostaPredicao:
    """Prevê, grava no histórico e só então responde."""
    previsto = plano.modelo.prever(plano.passo + plano.horizonte).iloc[
        plano.passo :
    ]
    return registrar_previsao(
        plano.modelo, plano.referencia, previsto, historico, cfg
    )


def prever(
    pedido: PedidoPredicao,
    modelos: CatalogoModelos,
    historico: Historico,
    cfg: Settings,
) -> RespostaPredicao:
    """Valida, prevê, grava no histórico e só então responde."""
    return executar(planejar(pedido, modelos, cfg), historico, cfg)


def registrar_previsao(  # noqa: PLR0913
    modelo: ModeloServido,
    referencia: date,
    previsto: pd.DataFrame,
    historico: Historico,
    cfg: Settings,
    *,
    recomendacao: str | None = None,
) -> RespostaPredicao:
    """Monta a resposta e a grava no histórico antes de devolvê-la.

    `recomendacao` é o resultado da regra, quando a chamada vem dela.
    """
    resposta = _responder(
        modelo,
        referencia,
        previsto,
        cfg.valores_unitarios[modelo.sku],
        datetime.now(ZoneInfo(cfg.fuso_horario)),
    )
    historico.registrar(_linhas(resposta, recomendacao))
    return resposta


def _limite(valor: float) -> float | None:
    """Limite `nan` (método `indisponivel`) vira `null`."""
    return None if isnan(valor) else float(valor)


def _responder(
    modelo: ModeloServido,
    referencia: date,
    previsto: pd.DataFrame,
    valor_unitario: float,
    data_geracao: datetime,
) -> RespostaPredicao:
    dias = DIAS_POR_PERIODO[modelo.granularidade]
    periodos = [
        PeriodoPrevisto(
            data_alvo=referencia + timedelta(days=dias * i),
            quantidade_prevista=float(linha['previsao']),
            valor_previsto=float(linha['previsao']) * valor_unitario,
            limite_inferior_80=_limite(linha['inferior_80']),
            limite_superior_80=_limite(linha['superior_80']),
            limite_inferior_95=_limite(linha['inferior_95']),
            limite_superior_95=_limite(linha['superior_95']),
        )
        for i, (_, linha) in enumerate(previsto.iterrows(), start=1)
    ]
    return RespostaPredicao(
        id_requisicao=str(uuid4()),
        sku=modelo.sku,
        granularidade=modelo.granularidade,
        data_referencia=referencia,
        data_geracao=data_geracao,
        valor_unitario=valor_unitario,
        versao_modelo=modelo.versao,
        hash_artefato=modelo.hash_artefato,
        origem_modelo=modelo.origem,
        experimento_id=modelo.experimento_id,
        run_id=modelo.run_id,
        periodos=periodos,
    )


def _linhas(
    resposta: RespostaPredicao, recomendacao: str | None
) -> list[LinhaHistorico]:
    geracao_utc = resposta.data_geracao.astimezone(UTC).replace(tzinfo=None)
    return [
        LinhaHistorico(
            id_requisicao=resposta.id_requisicao,
            sku=resposta.sku,
            granularidade=resposta.granularidade,
            data_geracao=geracao_utc,
            data_referencia=resposta.data_referencia,
            data_alvo=periodo.data_alvo,
            versao_modelo=resposta.versao_modelo,
            hash_artefato=resposta.hash_artefato,
            quantidade_prevista=periodo.quantidade_prevista,
            valor_unitario=resposta.valor_unitario,
            valor_previsto=periodo.valor_previsto,
            limite_inferior_80=periodo.limite_inferior_80,
            limite_superior_80=periodo.limite_superior_80,
            limite_inferior_95=periodo.limite_inferior_95,
            limite_superior_95=periodo.limite_superior_95,
            experimento_id=resposta.experimento_id,
            run_id=resposta.run_id,
            recomendacao=recomendacao,
        )
        for periodo in resposta.periodos
    ]
