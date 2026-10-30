from typing import Annotated

from fastapi import APIRouter, Depends

from case_mr_health.api.schemas.changelog import Changelog
from case_mr_health.api.servicos.changelog import ler_changelog
from case_mr_health.config import Settings

router = APIRouter(tags=['changelog'])


def obter_settings() -> Settings:
    return Settings()


@router.get(
    '/changelog',
    summary='Changelog estruturado do projeto',
    description=(
        'Devolve as versões do `CHANGELOG.md` gerado pelo towncrier, na ordem '
        'do arquivo, com data e mudanças por tipo. Cada mudança traz o texto '
        'e os IDs das issues ligadas. Changelog ausente ou vazio responde 200 '
        'com `versoes` vazia; conteúdo fora do formato é ignorado e vai para '
        'o log como aviso.'
    ),
    response_description='Versões do projeto; vazia se não houver changelog.',
)
def consultar_changelog(
    cfg: Annotated[Settings, Depends(obter_settings)],
) -> Changelog:
    return ler_changelog(cfg.changelog_path)
