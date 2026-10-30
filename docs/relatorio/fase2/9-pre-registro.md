# Pré-registro da validação das faixas de confiança (#9)

Status: **PROPOSTA**, escrito antes de calcular qualquer MASE por fold ou faixa. O que já era conhecido ao escrever: as tabelas de MAE e o desvio-padrão do MAE entre folds de `registro-fase2.md` (0,44 a 1,06 nas diárias; 3,5 a 11,9 nas semanais), que dão a ordem de grandeza da dispersão, e o resultado aritmético de que as faixas do meio têm largura 0,25.

## Unidade de análise

20 runs: 12 diários (3 baselines × 4 SKUs) e 8 semanais (2 baselines × 4 SKUs), seed 20261030, visão de desenvolvimento. Só baselines. O OOT não entra.

## Estatística

`x_1..x_n`: MASE de cada fold (escala de um passo, `metricas.py`, sem alteração). `mase` = média; `dp` = desvio-padrão amostral (ddof=1); `ep = dp/√n`; IC t bilateral de 80%: `mase ± t(0,90; n-1)·ep`, com limite inferior truncado em 0.

## Critério de instabilidade (fixado aqui)

**Instável** se o IC de 80% atravessa **duas ou mais** fronteiras de faixa (0,50, 0,75, 1,00), isto é, se a faixa do limite inferior e a do superior estão a duas ou mais faixas de distância. MASE instável resulta em Insuficiente (motivo `mase_instavel`), mantendo a faixa pontual como metadado.

Justificativa:

1. O critério pergunta o que importa ao gestor: o rótulo fica determinado pela evidência? Uma fronteira atravessada é uma ambiguidade entre faixas vizinhas, inevitável perto de um limite. Duas fronteiras significam que os dados não separam, por exemplo, Boa de Ruim.
2. Depende da posição, não só da dispersão: um MASE 2,0 ± 0,5 continua Ruim, pois há evidência de que é ruim.
3. 80%, e não 95%: com n = 4, o semi-intervalo de 95% é `3,18·dp/2 = 1,59·dp`; qualquer modelo com dp > 0,16 cruzaria duas fronteiras no meio da escala, por causa de n, não do modelo. O de 80% tem semi-intervalo `0,82·dp` (n = 4) e `0,69·dp` (n = 5). 80% também é o menor nível de intervalo do projeto.
4. O intervalo `média ± t·dp/√k` é o de estimativas por grupos de réplicas, com `k-1` graus de liberdade, e a própria fonte adverte que a estimativa de variância com 3 graus de liberdade "is not very stable" [@lohr_sampling, p. 294]. Ressalva: Lohr supõe grupos independentes; os folds compartilham treino e a série é autocorrelacionada, então a cobertura de 80% é nominal. O IC é usado como régua, não como garantia.

## Sensibilidades pré-declaradas (não mudam a classificação)

(a) IC de 95%; (b) saída de um fold (jackknife): faixas das médias sem cada fold, instável se elas distam duas ou mais faixas; (c) item C semanal sem a semana 07-19 e sem os folds 1 e 2.

## Critério de discriminação (fixado aqui)

As faixas **discriminam** nestes dados só se valerem as três condições, nos 20 runs, depois da regra de instabilidade:

- D1: pelo menos dois status distintos entre Ótima, Boa, Média e Ruim;
- D2: nenhum status (incluindo Insuficiente) tem 16 ou mais runs (80%);
- D3: pelo menos 10 runs (50%) têm status diferente de Insuficiente.

Relatado também sem a regra de instabilidade (só faixa pontual) e por granularidade. Se falhar: reportar e propor (critério de aceite da issue).

## Escala do MASE na diária (ADR 0006)

Calcular nos 12 runs diários `MAE / escala_lag1` e `MAE / escala_lag7`. A troca é **recomendada** se valer ao menos uma condição; senão, manter lag 1:

- E1: em 2 ou mais dos 4 SKUs, a mediana entre folds de `escala_lag7 / escala_lag1` fica fora de [0,90; 1,10];
- E2: a faixa pontual muda em 25% ou mais dos 12 runs (3 ou mais).

A escala não é escolhida pela classificação que produz; E2 mede o impacto, sem preferência de direção. A troca é decisão do usuário, pois altera números aprovados em D-006.

## Limite

Esta validação só vê baselines e precisa ser repetida depois de integrar #10 e #11.
