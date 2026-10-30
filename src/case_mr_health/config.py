from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração centralizada; sobrescrevível por `CASE_MR_HEALTH_*`."""

    model_config = SettingsConfigDict(
        env_prefix='CASE_MR_HEALTH_',
        env_file='.env',
        extra='ignore',
    )

    raw_dir: Path = Path('data/raw')
    db_path: Path = Path('data/processed/base.duckdb')
    relatorio_path: Path = Path('data/processed/relatorio_qualidade.md')
    arquivo_pedido: str = 'PEDIDO-_1_.xlsx'
    arquivo_item_pedido: str = 'ITEM_PEDIDO-_2_.xlsx'
    arquivo_sku: str = 'ITENS-_3_.xlsx'
    log_level: str = 'INFO'
