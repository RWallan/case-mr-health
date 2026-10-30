# Modelos servidos pelo MLflow Model Registry e histórico de previsões em DuckDB próprio

Treino e inferência são separados pelo MLflow Model Registry. Cada série tem um modelo registrado `demanda-<sku>-<granularidade>`, e há um experimento por granularidade, com tags `sku`, `granularidade` e `algoritmo`. Na inicialização, a API carrega a versão com alias `champion` de cada modelo, ou uma versão fixada por configuração, e nunca treina. As URIs de tracking (SQLite local) e de artefatos (diretório local) vêm de configuração, para permitir migrar para servidor e armazenamento remotos sem mudar código.

O histórico de previsões fica em um arquivo DuckDB exclusivo do serviço, separado do MLflow e dos dados analíticos. Assim, o registro de cada previsão (requisição, versão, hash do artefato, intervalos, confiança) não depende do histórico de experimentos.

## Consequências

- DuckDB não aceita escrita concorrente de vários processos, então o serviço roda com um único worker. Para a demonstração isso é aceitável; com uso real, o histórico precisaria migrar para um banco transacional.
- O hash do artefato é calculado no registro do modelo e conferido no carregamento.
