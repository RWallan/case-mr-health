# Glossário

| Termo | Significado no projeto |
| --- | --- |
| SKU | Produto identificado como item A, B, C ou D. |
| Granularidade | Frequência temporal da série: diária ou semanal. |
| Demanda | Quantidade registrada na base consolidada; neste projeto é aproximada por vendas observadas. |
| Data de referência | Última data considerada para iniciar uma previsão. Pode ser informada ou derivada dos dados disponíveis. |
| Horizonte | Número de períodos futuros solicitados. |
| OOT | Período temporal selado, fora do ajuste e da seleção, usado para avaliação final. |
| Backtest | Avaliação retrospectiva em várias origens temporais para comparar candidatos. |
| MASE | Erro absoluto escalado médio, métrica usada na seleção e na confiança interna. |
| Reajuste | Ajuste do modelo selecionado com os dados mais recentes antes de registrá-lo. |
| Lote | Previsão de vários SKUs em uma solicitação ou arquivo. |

Consulte `GLOSSARY.md` para o vocabulário normativo do repositório. A implementação das frequências e identificadores está em `src/case_mr_health/api/` e `src/case_mr_health/series/`.
