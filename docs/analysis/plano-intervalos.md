# Plano de intervalos de previsão (ticket #8)

Status: **APROVADO** (D-008), com a emenda pós-hoc D-009 na seção 7. Escrito em 2026-10-30, **antes** de calcular qualquer intervalo ou cobertura em dados reais. Nenhum valor de cobertura real foi visto para fixar estas regras; o que se conhecia dos dados reais eram as métricas pontuais dos baselines (D-006) e os tamanhos das séries (76 a 79 dias; 10 semanas; 4 a 5 folds). Decisão e justificativa resumidas no ADR 0007.

As regras abaixo não mudam depois de ver a cobertura real. Se mudarem, isso é desvio e precisa ser sinalizado como tal.

## 1. Regra de decisão: nativo calibrado ou empírico

Vale por execução (série × algoritmo × combinação de hiperparâmetros). O empírico é o padrão; o nativo precisa **se mostrar** calibrado (`issues/8.md`, `issues/1.md`).

Sejam `n` os pontos de teste do backtest, `k_ν` quantos caíram dentro do intervalo nativo de nível `ν` (limites já truncados e aninhados, inclusive nas pontas) e `ĉ_ν = k_ν / n`.

O intervalo nativo só é usado se **todas** as condições valerem:

- **R1 (disponível):** o previsor tem `intervalos_nativos` e devolveu limites válidos em todos os folds.
- **R2 (estimável):** `n >= ceil(1 / (1 - ν_max))`, isto é, `n >= 20` para 95%. Abaixo disso, o erro de um único ponto não cabe em 5% e a cobertura não consegue distinguir 95% de 100%. Consequência fixada de antemão: **na semanal (`n = 4`) o nativo nunca é considerado calibrado.**
- **R3 (compatível):** para todo `ν`, o nominal `ν` está dentro do intervalo de Wilson de 95% de `ĉ_ν`.
- **R4 (sem subcobertura material):** para todo `ν`, `ĉ_ν >= ν - 0,05`.

Caso contrário, usa-se o empírico. O motivo fica registrado: `calibrado`, `sem_nativo`, `amostra_insuficiente` ou `fora_da_faixa`.

**O que "calibrado" quer dizer aqui.** É um rótulo operacional: "não há evidência, nesta amostra, de descalibração relevante". Não é demonstração de calibração. Com `n = 28` e dependência dentro do fold, o teste tem pouco poder. R4 existe porque R3 sozinha aceitaria 19/28 = 68% para 80%; subcobertura é o lado caro numa decisão de estoque. Os 0,05 são escolha de julgamento (cerca de 1 a 2 pontos em 28 a 35), não saem da literatura.

**O empírico não tem portão.** Se a cobertura do empírico vier ruim, ela é relatada, não ajustada: nenhum fator de correção é calibrado a posteriori com os folds.

## 2. Mecanismo empírico

Usa só `criar`, `ajustar` e `prever`, portanto serve a qualquer `Previsor` sem código novo.

**Erros de origem móvel dentro do treino** [Williams e Goodman, 1971; @hyndman_fpp3, seção 5.10]. Dado o treino `y[:n]` e o horizonte `h`:

- origens `t` de `max(2, n - h - K + 1)` até `n - h`, com `K = 70` (`Settings.intervalo_max_origens`), o que na prática usa todas as origens destas séries;
- para cada origem: previsor novo, ajusta em `y[:t]`, prevê `h` períodos de uma vez (sem recursão, como o backtest), trunca em zero, guarda `e = y[t:t+h] - previsto`;
- origem cuja `ajustar`/`prever` falhe é pulada e contada (`intervalo_origens_falhas`).

**Sem vazamento:** no backtest, `y[:n]` é o treino do fold. O teste do fold não entra.

**Relação entre resíduos e horizonte.** Os erros são fora da amostra e de `1` a `h` passos à frente, gerados pela mesma previsão direta que o modelo usa, e não resíduos de um passo no treino. Resíduos de um passo só valem para `h = 1`; para `h > 1` a incerteza depende do método (`σ√h` no naive, `σ√(1 + 1/T)` na média, `σ√(k + 1)` no sazonal) [@hyndman_fpp3, seção 5.5, tabela 5.2], então não existe fator genérico como `√h` que sirva a todo `Previsor`.

Os erros dos `h` passos são **agrupados**, e a largura do intervalo é **constante no horizonte**. Motivos:

1. Amostra. Quantil por passo exigiria 39 erros por passo para 95% (seção 3), e há 34 a 64 origens por passo na diária e 4 a 7 na semanal.
2. Premissa apoiada na EDA aprovada: as diárias são estacionárias em nível, com autocorrelação fraca (#5; `candidatos.EVIDENCIAS`). Nesse caso a distribuição do erro quase não depende do passo: no naive com ruído i.i.d., `Var(y[t+j] - y[t]) = 2σ²` para todo `j`.

Risco aceito: com passeio aleatório ou tendência o agrupamento dá intervalo estreito nos passos longos e largo nos curtos. Na semanal a estacionariedade não é testável (`n = 10`), logo a premissa é hipótese. A cobertura é **marginal por ponto**, não conjunta na trajetória (a conjunta pediria correção de Bonferroni [Stankeviciute et al., 2021]).

Para o modelo registrado, `h` é o horizonte máximo servido (`oot_diaria_dias` = 14; `oot_semanal_semanas` = 2). Para o backtest, `h` é o tamanho do teste (7 ou 1).

## 3. Quantis ou t de Student

Decidido só pelo tamanho da amostra, nunca pela cobertura:

- **`empirico_quantil`**, se o número de erros `m >= ceil(2 / (1 - ν_max)) - 1` (39 para 95%). Limites assimétricos: `previsto + e(k)` e `previsto + e(m + 1 - k)`, com `e(i)` a estatística de ordem e `k = floor((m + 1)(1 - ν) / 2)`. É a correção de amostra finita do conformal split [Angelopoulos e Bates, seção 1, teorema 1] aplicada a cada cauda. Assimétrico porque a demanda é assimétrica e intermitente [@hyndman_fpp3, seção 5.5: sem normalidade, intervalos não simétricos].
- **`empirico_t`**, se `m < 39` e houver ao menos 2 origens: `previsto + ē ± t(1 - (1 - ν)/2; o - 1) · s · √(1 + 1/o)`, com `ē` e `s` da amostra de erros, `o` o número de origens. É o intervalo de predição clássico de uma nova observação normal [@kutner2005, p. 58; @johnson_wichern2007, p. 379, ambos com a regressão; aqui, o caso só com intercepto]. Usa `o`, não `m`, nos graus de liberdade: erros da mesma origem são dependentes.
- **`indisponivel`**, com menos de 2 origens válidas: limites `nan`, pontos fora da cobertura e tag registrada.

**Por que não conformal puro em toda parte.** Com `m` pequeno o quantil corrigido não existe: o conformal devolveria intervalo infinito. Usar o maior erro como 95% daria cobertura de no máximo `m/(m+1)`, ou seja, 80% com 4 erros, sob o rótulo de 95%. O `empirico_t` é finito e monótono no nível, ao custo de assumir normalidade, mais razoável na semanal (soma de 7 dias) que na diária, mas não verificável.

**Garantias.** Nenhuma é formal: conformal exige permutabilidade, que a série temporal e a sobreposição de origens violam [Barber et al., 2023, seção 1]. O `(m + 1)` é correção de amostra finita, não garantia. Peso maior para erros recentes (o caminho de Barber et al.) fica fora: 42 a 79 pontos não sustentam mais um parâmetro.

**Tamanhos resultantes (aritmética, sem olhar dados).**

| Situação | `n` | `h` | origens | erros `m` | Método |
| --- | --- | --- | --- | --- | --- |
| Diária, fold 1 | 42 | 7 | 34 | 238 | quantil |
| Diária, modelo final | 76 a 79 | 14 | 61 a 64 | 854 a 896 | quantil |
| Semanal, fold 1 | 6 | 1 | 4 | 4 | t, gl = 3 |
| Semanal, fold 4 | 9 | 1 | 7 | 7 | t, gl = 6 |
| Semanal, modelo final | 10 | 2 | 7 | 14 | t, gl = 6 |

**Primeiro fold semanal.** Com 6 pontos de treino, as origens são 2, 3, 4 e 5, e os ajustes têm 2 a 5 pontos. Saem 4 erros: 95% e 80% vêm do `empirico_t` com 3 graus de liberdade (multiplicadores 3,18 e 1,64, antes de `√1,25`). O intervalo tende a ser largo e pode ser indisponível para candidatos que não ajustam com tão poucos pontos; nesse caso, o fold fica fora da cobertura e isso aparece em `cobertura_n_pontos`.

**Revisão antes dos dados reais (2026-10-30).** A primeira versão deste plano limitava as origens a `K = 30`, por custo. Uma simulação em processos conhecidos (nenhum dado real; `docs/relatorio/fase2/8.md`) mostrou cobertura real de 90,7% para 95% com `n = 76`, `h = 14` e Poisson(1,5): com 14 passos, 30 origens tocam só 43 períodos distintos, e os 420 erros são muito menos informativos do que parecem. Com todas as origens, 94,0%. `K` passou a 70, ao custo de mais ajustes. Nenhuma cobertura real tinha sido calculada.

## 4. Pós-processamento (sempre em `intervalos.py`)

Vale para nativo e empírico, nesta ordem: trunca os limites em zero; garante que o intervalo contém a previsão pontual; garante o aninhamento (cada nível contém o nível menor). Ajustes só alargam.

## 5. Cobertura e como relatá-la

- `k/n` juntando os pontos dos folds, por nível, com intervalo de Wilson de 95%, recomendado para `n` pequeno [Brown, Cai e DasGupta, 2001]. Inclusivo nas pontas (a demanda é discreta).
- O Wilson supõe pontos independentes; dentro do fold eles não são. O intervalo é **otimista**, ou seja, a incerteza real é maior.
- A cobertura também é registrada por fold, além da amplitude média e de `cobertura_n_pontos`.
- Item C semanal: cobertura também sem a semana 07-19 (decisão 24 da Fase 1).
- Com `n = 4`, a cobertura só assume 0, 25, 50, 75 ou 100%: **calibração semanal não é estimável**.

**Não estimável neste ticket:** calibração semanal; calibração por passo ou por fold; passos 8 a 14 da diária e semana 2 da semanal (o backtest só prevê 7 dias e 1 semana; só o OOT, no #13, toca esses passos); cobertura conjunta da trajetória; cobertura condicional (por dia da semana, por nível).

## 6. Fora de escopo

Seleção de modelo (#12), cobertura no OOT (#13), resposta da API (#14). A cobertura não entra na escolha de candidato neste ticket.

## 7. Emenda D-009 (desvio pós-hoc)

**Isto é um desvio.** A emenda foi criada **depois** de ver a cobertura real, contrariando o aviso do início deste plano, e foi aprovada pelo usuário (D-009, 2026-10-30). As seções 1 a 6 ficam como foram escritas; a seção 4 passa a valer com o acréscimo abaixo.

**Regra.** Se a fração de zeros do treino for `>= (1 - ν)/2`, o limite inferior do nível `ν` é zero. Vale para empírico e nativo, no pós-processamento (`intervalos.normalizar`), antes de conter a previsão e aninhar. Usa só o treino do fold, ou todo o desenvolvimento no modelo final; a fração fica guardada na `Calibracao` e registrada em `intervalo.fracao_zeros`.

**Por quê.** Em séries com muitos zeros, a previsão mais o erro mais negativo dava limite inferior pouco acima de zero, excluindo os dias sem venda (`docs/relatorio/fase2/8.md`).

**Cuidado na leitura.** A regra nasceu dos mesmos folds em que a cobertura é medida, então a cobertura depois da emenda é **otimista** e não a valida. A avaliação independente é o OOT do #13.
