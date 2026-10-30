# Armazenamento

| Conteúdo | Componente | Observação |
| --- | --- | --- |
| Séries e dados de demonstração | arquivos locais configurados pelo projeto | Não contêm identificador de unidade; a previsão é agregada. |
| Modelos e versões | MLflow Tracking/Model Registry | Cada SKU e granularidade tem modelo registrado. Não altere os artefatos existentes para consultar ou servir previsões. |
| Histórico de previsões | DuckDB | Usado para manter consultas e comparações do dashboard. |
| Chave de LLM | variável de ambiente/configuração do backend | Não deve ser incorporada ao bundle do frontend nem registrada em logs. |

Os caminhos e URIs efetivos dependem da configuração em `src/case_mr_health/config.py`. O protocolo do registry/histórico é descrito no [ADR 0005](../decisoes/adr/0005-registry-mlflow-e-historico-em-duckdb.md). O armazenamento de dados e o reajuste são descritos no [ADR 0011](../decisoes/adr/0011-atualizacao-de-dados-pela-api-com-reajuste.md). Backups, retenção e alta disponibilidade não são definidos pela demonstração.
