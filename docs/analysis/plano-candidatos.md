# Plano pré-análise: tabela de candidatos por série (ticket #6)

Escrito antes de qualquer resultado de método. Este ticket **não treina nem ajusta modelos**: a tabela decide quem entra no backtest do #7 em diante. Direção aprovada pelo usuário em 2026-10-30 (decisão D-003). Dados: somente a visão de desenvolvimento (período OOT selado; ver `config.py` e `.ds-workflow/data-policy.json`).

Dispensa do plano completo: o usuário concordou em 2026-10-30 (item 5 da direção) que a própria tabela congelada faça o papel de plano. Este arquivo é a versão curta, congelada com `freeze`.

1. **Pergunta e objetivo.** Para cada uma das 8 séries (4 SKUs × diária e semanal), quais algoritmos entram no backtest, com quais premissas, base de decisão (evidência, hipótese ou decisão do usuário) e qual espaço de hiperparâmetros.

2. **População e desenho.** Venda da rede por SKU, 79 dias (A, C) e 76 dias (B, D) na diária; 10 semanas completas (06-07 a 08-15) na semanal. Folds de origem móvel e treino mínimo (42 dias; 6 semanas) já decididos no #4 e não reabertos.

3. **Hipóteses.**
   - Confirmatórias: nenhuma. O #6 não testa hipóteses novas; reaproveita os testes do #5.
   - Exploratórias (a verificar no backtest do #7 em diante, não aqui): (H1) o naive sazonal supera naive e média nas diárias B e C; (H2) em A e D o dia da semana ajuda, apesar do teste inconclusivo; (H3) Croston, SBA e TSB superam os baselines nas diárias; (H4) SES e Holt amortecido não superam naive e média nas semanais; (H5) o ARIMA mínimo não supera SES na semanal.

4. **Estimando.** Não há estimando inferencial. O produto é uma tabela de decisão.

5. **Regras de entrada e exclusão (fixadas agora).** Um candidato do universo do ADR 0003 entra numa série, a menos que:
   - (a) uma premissa estrutural tenha sido **refutada por teste do #5** nessa série;
   - (b) seja **aritmeticamente inviável** (por exemplo, ciclo sazonal que não cabe nos dados);
   - (c) o usuário tenha decidido excluí-lo.
   Ausência de evidência (teste inconclusivo ou não testável) **não exclui**: o candidato entra rotulado como **hipótese**. ARIMA_PLUS está fora (ADR 0003).

6. **Dados ausentes.** Dias sem venda são zeros imputados (decisão do #3). Sem tratamento adicional.

7. **Outliers e transformações.** Nenhuma alteração das séries. Item C semanal, semana 07-19 (40 unidades): manter o valor (alternativa 1, decisão 24 do registro). Requisito do backtest: relatar as métricas com e sem essa semana e com e sem os folds 1 e 2. Variável de intervenção e métricas robustas são complementos opcionais para candidatos que as aceitam (ARIMA semanal).

8. **Métodos e justificativa.**
   - Baselines: naive, média histórica expansiva do treino do fold e naive sazonal de lag 7 (diária).
   - ETS (SES, Holt-Winters aditivo, Holt amortecido), ARIMA e SARIMA via `statsmodels` 0.15.0; Prophet 1.5.0; Croston, SBA e TSB em implementação própria (ADR 0003; Syntetos e Boylan; Teunter, Syntetos e Babai).
   - Referências usadas na tabela são as do registro da Fase 1 (seção 7), sem acréscimo de páginas não consultadas.

9. **Premissas e como serão checadas.** Cada premissa é confrontada com um resultado do #5 por série e classificada como atendida, não atendida ou não testável; a base é "evidência" (teste do #5, com número) ou "hipótese". O notebook recalcula esses diagnósticos na visão de desenvolvimento e confere com os valores aprovados.

10. **Protocolo de validação.** Fora do escopo do #6 (feito no #7). Aqui só se fixa o requisito de sensibilidade do item C semanal.

11. **Métricas.** Fora do escopo. Os critérios (MAE, MSE, RMSE, WAPE, MASE) são os do #7.

12. **Critério de comparação.** Fora do escopo: o #6 não escolhe vencedor. Regra de simplicidade a manter no #7: em empate, vale o candidato com menos parâmetros.

13. **Multiplicidade.** Teto de **4 combinações de hiperparâmetros por candidato**, sem busca automática de ordem, hiperparâmetros fixados na tabela antes de ver resultados. Com 4 a 5 folds de teste, o risco de escolha por acaso cresce com o número de candidatos; isso será dito no #7.

14. **Sensibilidade.** Item C semanal, como no item 7.

15. **Avaliação final.** O OOT só é lido no #13.

16. **Limitações previsíveis.** 76 a 79 dias e 10 semanas; testes do #5 exploratórios; estacionariedade e autocorrelação semanais não testáveis; sazonalidade de A e D inconclusiva (poder baixo); venda é proxy de demanda e ruptura aparece como zero; ADR 0003 prevê ARIMA/SARIMA/ETS no universo, e a exclusão de SARIMA semanal é aritmética (ciclo de 4 ou 52 semanas não cabe em 10 pontos).

17. **Registro de desvios.** (vazio)

## Catálogo congelado

### Diárias (A, B, C, D; todas intermitentes)

| Candidato | Entra | Hiperparâmetros (máx. 4 combinações) |
| --- | --- | --- |
| Naive | sim (baseline) | nenhum |
| Média histórica | sim (baseline) | nenhum |
| Naive sazonal (lag 7) | sim (B, C: evidência; A, D: hipótese) | período = 7 |
| ETS: SES | sim | α estimado no treino do fold |
| ETS: Holt-Winters aditivo | sim (sazonal: B, C evidência; A, D hipótese) | período = 7, sem tendência, sem multiplicativo |
| ARIMA (sem sazonal) | sim (contraste) | (p, d, q) ∈ {(1,0,0), (0,0,1), (1,0,1)}, com constante |
| SARIMA | sim (sazonal: B, C evidência; A, D hipótese) | não sazonal ∈ {(0,0,0), (1,0,0), (0,0,1)} × sazonal (1,0,0,7) |
| Croston | sim | α ∈ {0,1; 0,2; 0,3} |
| SBA | sim | α ∈ {0,1; 0,2; 0,3} |
| TSB | sim | α = β ∈ {0,1; 0,2; 0,3} |
| Prophet | sim | só sazonalidade semanal; sem anual, mensal nem feriados; tendência linear sem pontos de mudança; ordem de Fourier ∈ {2, 3} × escala a priori da sazonalidade ∈ {1; 10} |

Observação: o sazonal (0,0,0,7) citado na direção coincide com o ARIMA sem sazonal; por isso o SARIMA usa apenas o termo sazonal (1,0,0,7). Isto é uma interpretação do agente da direção aprovada e está sinalizada para o usuário.

### Semanais (A, B, C, D; todas suaves, 10 semanas)

| Candidato | Entra | Hiperparâmetros |
| --- | --- | --- |
| Naive | sim (baseline) | nenhum |
| Média histórica | sim (baseline) | nenhum |
| Naive sazonal | **não** (sem sazonalidade testável; ciclo de 4 ou 52 semanas não cabe) | — |
| ETS: SES | sim | α estimado |
| ETS: Holt amortecido | sim | φ estimado em [0,8; 0,98] |
| ARIMA mínimo | sim (decisão do usuário, para contraste; base fraca) | (p, d, q) ∈ {(1,0,0) com constante, (0,1,1) sem constante} |
| SARIMA | **não** (aritmética) | — |
| Croston, SBA, TSB | **não** (ADI = 1, sem intermitência) | — |
| Prophet | **não** (decisão do usuário) | — |

Item C semanal: ARIMA mínimo pode ter uma variante com variável de intervenção na semana 07-19 (complemento opcional, não conta nas 4 combinações).
