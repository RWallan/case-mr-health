"""Atualização de dados pela API: ingestão síncrona, reajuste em segundo plano.

A validação dos arquivos acontece na própria requisição (erros com planilha
e linha). Só o reajuste das séries roda em segundo plano, uma atualização
por vez (ADR 0005, ADR 0011). A trava de uma atualização só é solta quando
o reajuste termina, e a API passa a servir cada versão nova assim que ela
é registrada.
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import duckdb
from loguru import logger

from case_mr_health.api.erros import (
    AtualizacaoInexistente,
    AtualizacaoRecusada,
    DadosInvalidos,
)
from case_mr_health.api.mlflow_cliente import SemVersao
from case_mr_health.api.modelos import CatalogoModelos, recarregar_serie
from case_mr_health.api.schemas.atualizacao import (
    RespostaAtualizacao,
    SerieAtualizada,
)
from case_mr_health.api.schemas.erros import DetalheErro
from case_mr_health.atualizacao import (
    AtualizacaoRepetidaError,
    Ingestao,
    ingerir_pedidos,
)
from case_mr_health.candidatos import SKUS
from case_mr_health.config import Settings
from case_mr_health.dados import DadosInvalidosError
from case_mr_health.particoes import GRANULARIDADES
from case_mr_health.reajuste import reajustar_serie

_LINHA = re.compile(r'^(?P<campo>\w+ linha \d+): (?P<mensagem>.+)$')


def detalhes_do_erro(erro: DadosInvalidosError) -> list[DetalheErro]:
    """Cada linha `PLANILHA linha N: texto` vira um detalhe campo/mensagem."""
    detalhes = []
    for linha in str(erro).splitlines()[1:] or [str(erro)]:
        achada = _LINHA.match(linha)
        if achada:
            detalhes.append(DetalheErro(**achada.groupdict()))
        else:
            detalhes.append(DetalheErro(campo='arquivo', mensagem=linha))
    return detalhes


class GerenteAtualizacoes:
    def __init__(self, cfg: Settings, catalogo: CatalogoModelos):
        self._cfg = cfg
        self._catalogo = catalogo
        self._ocupado = threading.Lock()
        self._atualizacoes: dict[str, RespostaAtualizacao] = {}
        self._executor = ThreadPoolExecutor(max_workers=1)

    def fechar(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def obter(self, id_atualizacao: str) -> RespostaAtualizacao:
        try:
            return self._atualizacoes[id_atualizacao].model_copy(deep=True)
        except KeyError:
            raise AtualizacaoInexistente(
                f'Atualização {id_atualizacao} desconhecida.'
            ) from None

    def iniciar(self, pedidos: bytes, itens: bytes) -> RespostaAtualizacao:
        """Valida e aplica os arquivos; o reajuste segue em segundo plano."""
        if not self._ocupado.acquire(blocking=False):
            raise AtualizacaoRecusada(
                'Já existe uma atualização em andamento; aguarde o fim.'
            )
        try:
            ingestao = self._ingerir(pedidos, itens)
        except BaseException:
            self._ocupado.release()
            raise
        atualizacao = RespostaAtualizacao(
            id=uuid4().hex,
            estado='em_andamento',
            hash_dados=ingestao.hash_dados,
            pedidos_novos=ingestao.pedidos_novos,
            itens_novos=ingestao.itens_novos,
            ultimo_dia=ingestao.ultimo_dia,
            iniciada_em=datetime.now(UTC),
            concluida_em=None,
            series=[],
        )
        self._atualizacoes[atualizacao.id] = atualizacao
        self._executor.submit(self._reajustar, atualizacao.id)
        return atualizacao.model_copy(deep=True)

    def _ingerir(self, pedidos: bytes, itens: bytes) -> Ingestao:
        with TemporaryDirectory() as pasta:
            caminho_pedidos = Path(pasta) / 'pedido.xlsx'
            caminho_itens = Path(pasta) / 'item_pedido.xlsx'
            caminho_pedidos.write_bytes(pedidos)
            caminho_itens.write_bytes(itens)
            try:
                return ingerir_pedidos(
                    self._cfg, caminho_pedidos, caminho_itens
                )
            except DadosInvalidosError as erro:
                raise DadosInvalidos(
                    'As planilhas não passaram na validação; nada foi '
                    'aplicado.',
                    detalhes=detalhes_do_erro(erro),
                ) from erro
            except AtualizacaoRepetidaError as erro:
                raise AtualizacaoRecusada(str(erro)) from erro
            except duckdb.Error as erro:
                raise DadosInvalidos(
                    'Não foi possível ler as planilhas como XLSX.',
                    detalhes=[
                        DetalheErro(campo='arquivo', mensagem=str(erro))
                    ],
                ) from erro

    def _reajustar(self, id_atualizacao: str) -> None:
        atualizacao = self._atualizacoes[id_atualizacao]
        try:
            for sku in SKUS:
                for granularidade in GRANULARIDADES:
                    atualizacao.series.append(
                        self._reajustar_serie(
                            sku, granularidade, atualizacao.hash_dados
                        )
                    )
        finally:
            atualizacao.estado = _estado_final(atualizacao.series)
            atualizacao.concluida_em = datetime.now(UTC)
            self._ocupado.release()

    def _reajustar_serie(
        self, sku: str, granularidade: str, hash_dados: str
    ) -> SerieAtualizada:
        serie = {'sku': sku, 'granularidade': granularidade}
        try:
            reajuste = reajustar_serie(
                self._cfg, sku, granularidade, hash_dados
            )
            if reajuste.promovida:
                recarregar_serie(self._cfg, self._catalogo, sku, granularidade)
        except SemVersao as erro:
            return SerieAtualizada(**serie, estado='ignorada', erro=str(erro))
        # O reajuste de uma série não pode derrubar as demais.
        except Exception as erro:  # noqa: BLE001
            logger.exception('{}/{}: {}', sku, granularidade, erro)
            return SerieAtualizada(**serie, estado='falhou', erro=str(erro))
        return SerieAtualizada(
            **serie,
            estado='reajustada',
            versao_anterior=reajuste.versao_anterior,
            versao_nova=reajuste.versao_nova,
            servida=reajuste.promovida,
        )


def _estado_final(series: list[SerieAtualizada]) -> str:
    falhas = sum(s.estado == 'falhou' for s in series)
    if falhas == 0:
        return 'concluida'
    return 'falhou' if falhas == len(series) else 'concluida_com_erros'
