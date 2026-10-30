# Candidatos de algoritmo: métodos de demanda intermitente incluídos, ARIMA_PLUS excluído

Entre 33% e 46% dos dias de cada SKU não têm venda na visão de desenvolvimento (30% a 43% no histórico completo, com o calendário do SKU), e há um efeito forte de fim de semana (vendas cerca de 2,4 vezes maiores de sexta a domingo na rede; EDA do ticket #5). Por isso o conjunto de candidatos inclui, além de ARIMA/SARIMA/ETS (via `statsmodels`) e dos baselines, os métodos clássicos de demanda intermitente: Croston, SBA (Syntetos e Boylan) e TSB (Teunter, Syntetos e Babai). Eles não estavam na especificação original. São implementados em código próprio para evitar `numba`/`statsforecast` no Python 3.14.

O ARIMA_PLUS foi excluído porque é exclusivo do BigQuery ML e a infraestrutura é local, com DuckDB. O Prophet só entra se instalar sem problemas no Python 3.14; com cerca de 90 dias de histórico, apenas a sazonalidade semanal dele seria utilizável.

A escolha final por série depende da EDA (Fase 1). Um candidato só é considerado se suas premissas forem atendidas.
