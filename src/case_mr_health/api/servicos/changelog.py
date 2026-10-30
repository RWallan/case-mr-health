import re
from datetime import date
from pathlib import Path

from loguru import logger

from case_mr_health.api.schemas.changelog import (
    Changelog,
    Item,
    Secao,
    TipoMudanca,
    Versao,
)

_VERSAO = re.compile(
    r'# \S+ (?P<versao>\d+\.\d+\.\d+\S*) \((?P<data>\d{4}-\d{2}-\d{2})\)'
)
_LINK_ISSUE = r'\[#(\d+)\]\(issues/\1\.md\)'
# O towncrier fecha o item com `([#1](issues/1.md), [#2](issues/2.md))`.
_LINKS_FINAIS = re.compile(
    r'\s*\(\s*\[#\d+\]\(issues/\d+\.md\)'
    r'(?:\s*,\s*\[#\d+\]\(issues/\d+\.md\))*\s*\)$'
)
# Um fragmento de várias linhas sai indentado, às vezes com linha em branco.
_CONTINUACAO = re.compile(r'\n(?:[ \t]*\n)*[ \t]+(?=\S)')


def ler_changelog(caminho: Path) -> Changelog:
    """Lê o `CHANGELOG.md` do towncrier.

    Arquivo ausente, vazio ou fora do formato gera aviso, nunca exceção: o
    changelog é informativo e a sua falta não é erro de servidor.
    """
    try:
        texto = caminho.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as erro:
        logger.warning('Changelog indisponível em {}: {}', caminho, erro)
        return Changelog(versoes=[])

    if not texto.strip():
        logger.warning('Changelog vazio em {}', caminho)
        return Changelog(versoes=[])

    return Changelog(versoes=_interpretar(texto))


def _interpretar(texto: str) -> list[Versao]:
    versoes: list[Versao] = []
    versao: Versao | None = None
    secao: Secao | None = None

    for bruta in _CONTINUACAO.sub(' ', texto).splitlines():
        linha = bruta.rstrip()
        if linha.startswith('# '):
            versao, secao = _ler_versao(linha), None
            if versao:
                versoes.append(versao)
        elif linha.startswith('## ') and versao:
            secao = _ler_secao(linha)
            if secao:
                versao.secoes.append(secao)
        elif linha.startswith('- ') and secao:
            secao.itens.append(_ler_item(linha))
        elif linha:
            _avisar(linha)

    return versoes


def _ler_versao(linha: str) -> Versao | None:
    encontrada = _VERSAO.fullmatch(linha)
    if not encontrada:
        _avisar(linha)
        return None

    try:
        data = date.fromisoformat(encontrada['data'])
    except ValueError:
        _avisar(linha)
        return None

    return Versao(versao=encontrada['versao'], data=data, secoes=[])


def _ler_secao(linha: str) -> Secao | None:
    try:
        tipo = TipoMudanca(linha.removeprefix('## ').strip())
    except ValueError:
        _avisar(linha)
        return None

    return Secao(tipo=tipo, itens=[])


def _ler_item(linha: str) -> Item:
    texto = linha.removeprefix('- ').strip()
    issues = dict.fromkeys(int(id_) for id_ in re.findall(_LINK_ISSUE, texto))
    return Item(texto=_LINKS_FINAIS.sub('', texto), issues=list(issues))


def _avisar(linha: str) -> None:
    logger.warning('Linha do changelog fora do formato: {}', linha)
