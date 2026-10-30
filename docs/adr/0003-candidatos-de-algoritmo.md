# Candidatos de algoritmo: métodos de demanda intermitente incluídos, ARIMA_PLUS excluído

Entre 32% e 43% dos dias de cada SKU não têm venda, e há um efeito forte de fim de semana. Por isso o conjunto de candidatos inclui, além de ARIMA/SARIMA/ETS (via `statsmodels`) e dos baselines, os métodos clássicos de demanda intermitente: Croston, SBA e TSB (Syntetos & Boylan). Eles não estavam na especificação original. São implementados em código próprio para evitar `numba`/`statsforecast` no Python 3.14.

O ARIMA_PLUS foi excluído porque é exclusivo do BigQuery ML e a infraestrutura é local, com DuckDB. O Prophet só entra se instalar sem problemas no Python 3.14; com cerca de 90 dias de histórico, apenas a sazonalidade semanal dele seria utilizável.

A escolha final por série depende da EDA (Fase 1). Um candidato só é considerado se suas premissas forem atendidas.
