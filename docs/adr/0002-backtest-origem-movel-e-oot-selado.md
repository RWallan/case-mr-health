# Backtest com origem móvel e OOT selado no lugar de um corte único de teste

As séries são curtas: cerca de 90 dias na granularidade diária e 12 semanas completas na semanal. Um único corte de teste deixaria poucos pontos e métricas instáveis. Por isso cada série reserva um período final como OOT, que só é usado na validação final (Fase 4). No restante, o "teste" é um backtest com origem móvel e janela expansiva, e as métricas de teste são a média dos folds.

- Diária: OOT com os últimos 14 dias (dois ciclos semanais) e folds de 7 dias.
- Semanal: OOT com as últimas 2 semanas, folds de 1 semana e treino mínimo de cerca de 6 semanas.

## Consequências

- Toda transformação com parâmetros estimados é ajustada dentro de cada fold, apenas com o treino do fold.
- As datas exatas das partições são definidas por série na Fase 1 e registradas no MLflow.
- O OOT semanal tem só 2 pontos. Ele serve para detectar degradação grosseira, não para dar evidência estatística forte.
