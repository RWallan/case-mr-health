from pathlib import Path

from pydantic import Field
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
    desenvolvimento_db_path: Path = Path(
        'data/processed/desenvolvimento.duckdb'
    )
    oot_db_path: Path = Path('data/processed/oot.duckdb')
    changelog_path: Path = Path('CHANGELOG.md')
    arquivo_pedido: str = 'PEDIDO-_1_.xlsx'
    arquivo_item_pedido: str = 'ITEM_PEDIDO-_2_.xlsx'
    arquivo_sku: str = 'ITENS-_3_.xlsx'
    log_level: str = 'INFO'
    # Partições (ADR 0002); o treino mínimo diário foi decidido no ticket #4.
    oot_diaria_dias: int = 14
    oot_semanal_semanas: int = 2
    fold_diaria_dias: int = 7
    fold_semanal_semanas: int = 1
    treino_minimo_diaria_dias: int = 42
    treino_minimo_semanal_semanas: int = 6
    # Treino e MLflow (ADR 0005); a seed padrão é a data local (YYYYMMDD).
    seed: int | None = None
    fuso_horario: str = 'America/Sao_Paulo'
    mlflow_tracking_uri: str = 'sqlite:///data/mlflow/mlflow.db'
    mlflow_artifact_dir: Path = Path('data/mlflow/artefatos')
    # Intervalos de previsão (#8, docs/analysis/plano-intervalos.md).
    niveis_intervalo: tuple[float, ...] = (0.80, 0.95)
    intervalo_max_origens: int = 70

    # API (#14, ADR 0005). `modelos_fixados`: nome do modelo → versão; o que
    # não estiver aqui serve o alias `champion`. O valor unitário vem daqui
    # porque a tabela `sku` só existe no `base.duckdb`, selado (spec, Dados).
    modelos_fixados: dict[str, str] = Field(default_factory=dict)
    valores_unitarios: dict[str, float] = Field(
        default_factory=lambda: {
            'item A': 10,
            'item B': 15,
            'item C': 20,
            'item D': 25,
        }
    )
    historico_db_path: Path = Path('data/servico/historico.duckdb')
    api_host: str = '127.0.0.1'
    api_port: int = 8000
