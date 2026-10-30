# Avaliação final no OOT (#13)

Uma única abertura do OOT, conforme `docs/analysis/protocolo-avaliacao-final.md`. Comparação descritiva com a média do backtest do mesmo run; sem teste de hipótese, sem intervalo de confiança e sem confiança de modelo (D-020). O MASE do OOT usa a escala do naive de um passo de todo o desenvolvimento; o do backtest usa a de cada treino de fold, logo os dois MASE não são diretamente comparáveis.

| Série | Algoritmo (versão) | Períodos | MAE OOT / backtest | RMSE OOT / backtest | WAPE OOT / backtest | MASE OOT / backtest | Cobertura 80% OOT / backtest | Cobertura 95% OOT / backtest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| item A diaria | naive_sazonal (6) | 14 | 2,500 / 2,143 | 3,284 / 2,791 | 1,129 / 0,897 | 1,010 / 0,811 | 1,000 / 1,000 | 1,000 / 1,000 |
| item B diaria | tsb (17) | 14 | 1,716 / 2,369 | 1,914 / 2,929 | 1,413 / 1,592 | 0,607 / 0,821 | 1,000 / 0,893 | 1,000 / 0,929 |
| item C diaria | media_historica (5) | 14 | 1,814 / 2,813 | 1,958 / 3,125 | 0,747 / 1,111 | 0,667 / 1,005 | 1,000 / 0,829 | 1,000 / 1,000 |
| item D diaria | sarima (9) | 14 | 2,041 / 2,033 | 2,490 / 2,466 | 0,649 / 0,730 | 0,657 / 0,682 | 0,857 / 0,929 | 0,929 / 0,929 |
| item A semanal | media_historica (4) | 2 | 3,500 / 3,933 | 3,614 / 3,933 | 0,226 / 0,267 | 0,516 / 0,664 | 1,000 / 0,750 | 1,000 / 1,000 |
| item B semanal | media_historica (4) | 2 | 5,500 / 6,750 | 7,433 / 6,750 | 0,440 / 0,687 | 0,500 / 0,605 | 1,000 / 1,000 | 1,000 / 1,000 |
| item C semanal | media_historica (4) | 2 | 6,500 / 9,236 | 6,862 / 9,236 | 0,448 / 0,430 | 0,750 / 1,877 | 0,500 / 0,500 | 1,000 / 0,750 |
| item D semanal | media_historica (4) | 2 | 1,500 / 4,699 | 1,655 / 4,699 | 0,077 / 0,205 | 0,300 / 0,963 | 1,000 / 0,750 | 1,000 / 1,000 |

## Limitações

- Séries semanais têm 2 pontos no OOT: servem para notar degradação grosseira, não como evidência estatística (ADR 0002).
- Séries diárias têm 14 pontos, autocorrelacionados; a cobertura observada tem granularidade de 1/14.
- Nenhum `champion` foi atribuído: a publicação por série é decisão do usuário (`case-mr-health promover`).
