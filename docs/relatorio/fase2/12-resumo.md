# Resumo da seleção por série (#12)

Rodada `3051af2281b74935981b7ccf6d98e7f8`. Critério: `12-pre-registro.md`. Só backtest.

| Série | Vencedor | Baseline | MAE | MAE baseline | d̄ | ep | MASE | Cobertura 80/95 | Confiança | Ganho pareado | Sinais |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| item A diaria | naive_sazonal {'periodo': '7'} | naive_sazonal | 2.143 | 2.143 | +0.000 | 0.000 | 0.811 | 1.00 / 1.00 | Média | É o baseline | menor RMSE: ets_holt_winters_aditivo |
| item A semanal | media_historica {} | media_historica | 3.933 | 3.933 | +0.000 | 0.000 | 0.664 | 0.75 / 1.00 | Insuficiente | É o baseline | - |
| item B diaria | tsb {'alfa_beta': '0.2'} | naive_sazonal | 2.369 | 2.536 | +0.167 | 0.089 | 0.821 | 0.89 / 0.93 | Insuficiente | Supera | menor RMSE: sarima; viés relativo +25.2% |
| item B semanal | media_historica {} | media_historica | 6.750 | 6.750 | +0.000 | 0.000 | 0.605 | 1.00 / 1.00 | Insuficiente | É o baseline | menor RMSE: ets_ses; viés relativo +31.8% |
| item C diaria | media_historica {} | media_historica | 2.813 | 2.813 | +0.000 | 0.000 | 1.005 | 0.83 / 1.00 | Ruim | É o baseline | menor RMSE: sarima; viés relativo -25.5% |
| item C semanal | media_historica {} | media_historica | 9.236 | 9.236 | +0.000 | 0.000 | 1.877 | 0.50 / 0.75 | Insuficiente | É o baseline | viés relativo -22.3% |
| item D diaria | sarima {'ordem': '(0, 0, 0)', 'ordem_sazonal': '(1, 0, 0, 7)'} | media_historica | 2.033 | 2.072 | +0.040 | 0.020 | 0.682 | 0.93 / 0.93 | Insuficiente | Supera | - |
| item D semanal | media_historica {} | media_historica | 4.699 | 4.699 | +0.000 | 0.000 | 0.963 | 0.75 / 1.00 | Insuficiente | É o baseline | menor RMSE: ets_ses |

Utilidade da confiança: {'I1': True, 'I2': False, 'I3': True, 'fora_de_insuficiente': 2, 'inutil': True}
