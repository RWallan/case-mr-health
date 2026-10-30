# Pré-registro da seleção por série e da utilidade da confiança (#12)

Status: **PROPOSTA**, aguarda aprovação do usuário. Escrito em 2026-10-30 antes de qualquer métrica de candidato. O que já era conhecido ao escrever: as métricas dos 20 runs de baselines (`registro-fase2.md`, seção 3.1; `fase2/9.md`). O MLflow local tem só esses 20 runs (contagem por papel, sem ler métricas): nenhum candidato foi avaliado nos dados reais deste repositório. Os smokes do #10 e do #11 ficaram nos worktrees e suas métricas não foram lidas.

## 1. Universo

Runs `FINISHED` da execução única do `treinar --todas` (tag `rodada`, seed 20261030), no commit integrado, sem árvore suja. São 72 runs previstos: 15 por série diária e 3 por série semanal. Runs `FAILED` ficam fora (D-016). Sai também o run com `intervalo_metodo = indisponivel`, pois não pode ser servido com os limites que a spec exige. Runs antigos, sem `rodada`, não entram.

**Premissas.** Premissa violada não exclui (plano do #6, item 5: só a refutação estrutural, já aplicada na tabela). Os testes têm pouco poder em 76 a 79 pontos, e o critério é o desempenho fora da amostra. Premissas não atendidas do vencedor vão para o resumo como limitação. Isso continua a divergência entre o ADR 0003 e o plano do #6 apontada em `fase2/11.md`.

## 2. Regra de seleção (por série, só no backtest)

Métrica primária: **MAE médio dos folds**, em unidades da série, com todos os folds. Comparação sempre dentro da série.

1. Baseline de referência `B*`: o de menor MAE médio na série.
2. Para cada candidato `c`, nos mesmos folds: `d_i = MAE_B*,i - MAE_c,i`, `d̄` = média e `ep = dp(d)/√n` (`ddof = 1`).
3. `c` **supera** `B*` se `d̄ > 0` e `d̄ > ep`.
4. Se ninguém supera, **o modelo da série é `B*`**, e isso é reportado como resultado. Se há algum, vence o de menor MAE médio entre os que superam.
5. Empate (diferença até `1e-9`): menos parâmetros, na ordem `naive`, `media_historica`, `naive_sazonal`, `ets_ses`, `sba`, `croston`, `tsb`, `ets_holt_winters_aditivo`, `sarima`, e depois a menor suavização.

Justificativa:
- Métodos simples são benchmark, e um método novo que não os supera não vale a pena [Hyndman e Athanasopoulos, FPP3, seção 5.2].
- A regra de um erro-padrão prefere o modelo mais simples quando o desempenho é comparável [documentação do scikit-learn, exemplo "Balance model complexity and cross-validated score", que cita Hastie, Tibshirani e Friedman]. Aqui ela é **adaptada**: em vez de medir a distância ao melhor, exige que o candidato se afaste do baseline em mais de um erro-padrão da diferença pareada. A adaptação é escolha do agente, sem fonte direta.
- Pareado, porque os folds têm dificuldades muito diferentes (dp do MAE entre folds de até 11,9) e todos os modelos veem os mesmos folds.
- Não é teste de hipótese: com 4 a 5 folds, 3 ou 4 graus de liberdade e folds dependentes, um teste quase não teria poder. A régua de 1 ep corresponde a `t > 1` e é propositalmente fraca. Serve de freio contra a escolha por acaso entre 12 candidatos, não de prova de superioridade.

## 3. O que é reportado e não decide

Por série: vencedor, MAE, RMSE, WAPE, MASE e viés (`média de previsto - observado`) do vencedor e de `B*`; `d̄` e `ep`; número de candidatos comparados; cobertura e amplitude dos intervalos; confiança; premissas não atendidas.

- **Sinalização, sem mudar o vencedor:** se o vencedor por RMSE for outro, ou se o viés relativo passar de 20% da venda média. O MAE é minimizado pela mediana, então em séries com muitos zeros ele pode favorecer previsões baixas; Kolassa (2016) argumenta que medidas de erro pontual são inadequadas para dados de contagem (lido só o resumo).
- **Item C semanal:** a decisão usa todos os folds (decisão 24 do registro da Fase 1 mantém a semana 07-19). Relata-se o MAE sem a semana e sem os folds 1 e 2, e sinaliza-se se o vencedor mudaria.
- **Entre granularidades:** só MASE e WAPE, nunca MAE (história 45).

## 4. Critério de confiança "inútil"

Aplicado aos **8 modelos selecionados**, que são o que o gestor verá; os 72 runs ficam como complemento, com D1 a D3 do `9-pre-registro.md`. A confiança é **inútil** se valer ao menos uma condição:

- I1: menos de 4 dos 8 modelos fora de Insuficiente;
- I2: menos de 2 faixas distintas entre os modelos fora de Insuficiente;
- I3: nenhum dos 4 modelos semanais fora de Insuficiente (o ADR 0004 baseia a recomendação na série semanal).

Aviso: nos baselines, os 8 runs semanais foram Insuficiente, então I3 tem chance alta de disparar. Isso é conhecido e declarado aqui. Se disparar, a decisão entre manter, trocar ou remover vai ao usuário.

## 5. Alternativa pareada (testada agora, só nos baselines)

Para o modelo `m` contra um baseline `b`, nos mesmos folds: `ganho = d̄ / MAE_b` (equivalente a `1 - MAE_m/MAE_b` sobre as médias, sem dividir por fold de MAE zero), IC t de 80% de `d̄` dividido por `MAE_b`. Status: **Supera** (IC inferior > 0), **Pior** (IC superior < 0) ou **Indistinguível**.

No teste com baselines, `b` = naive; são 12 comparações (média e naive sazonal na diária, média na semanal). Depois, nos 8 selecionados, `b = B*`; quem é o próprio baseline recebe "É o baseline". A alternativa é considerada informativa se, nos 12 pares, ao menos 3 ficarem fora de Indistinguível. Relatado também por granularidade. Limite: comparar um baseline com outro não mede a mesma coisa que comparar um candidato.

## 6. Reprodução e desvios

Treino real uma única vez (`plano-paralelizacao.md`, seção 5). Nenhum resultado altera este arquivo: desvio vai para `docs/relatorio/fase2/12.md` como desvio.

## Referências

- Hyndman e Athanasopoulos, *Forecasting: Principles and Practice*, 3ª ed., seção 5.2, `https://otexts.com/fpp3/simple-methods.html`, lida via WebFetch (resumo do conteúdo).
- scikit-learn, exemplo `plot_grid_search_refit_callable`, lido via WebFetch. O código do exemplo usa desvio-padrão entre splits, e não o erro-padrão: aqui usa-se o erro-padrão.
- Hastie, Tibshirani e Friedman, *The Elements of Statistical Learning*: **não consultado**; biblioteca local sem trecho sobre a regra.
- Kolassa (2016), *International Journal of Forecasting* 32(3), 788-803: só o resumo, via busca; o texto completo não foi lido.
