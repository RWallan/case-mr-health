# Intervalos de previsão empíricos por origem móvel, com nativo só se calibrado

Status: **APROVADO** pelo usuário (plano: D-008; emenda do piso zero: D-009; 2026-10-30).

Todo modelo precisa de intervalos de 80% e 95%, com poucos dados e sem depender do algoritmo. O padrão é um mecanismo empírico que usa só `ajustar` e `prever`: dentro do treino, cada origem móvel prevê de uma vez `h` períodos, e os erros de 1 a `h` passos, agrupados, formam os limites. Com erros suficientes (39 para 95%), usam-se quantis assimétricos; com poucos, o intervalo de predição t de Student. O método depende só do tamanho da amostra. O intervalo nativo (`intervalos_nativos`, opcional) só substitui o empírico se passar por uma regra fixada antes de olhar a cobertura real: disponível, `n >= 20`, nominal dentro do intervalo de Wilson e subcobertura de no máximo 5 pontos. Logo, na semanal (4 pontos) nunca é usado. Detalhes: `docs/analysis/plano-intervalos.md`.

## Opções consideradas

- **Resíduos de um passo no treino:** subestimam o erro em horizontes longos; só valem para `h = 1` [Hyndman e Athanasopoulos, FPP3, seção 5.5].
- **Escalar por `√h`:** vale para o naive em passeio aleatório, não para qualquer `Previsor`.
- **Quantil por passo:** exigiria 39 erros por passo, e há no máximo 64 na diária e 7 na semanal; na diária, o ganho sobre o agrupamento é pequeno e a variância do limite, maior.
- **Conformal puro em toda parte:** com poucos erros, o intervalo seria infinito; usar o maior erro como 95% cobriria no máximo `m/(m+1)`.
- **Bootstrap de resíduos:** exige resíduos não correlacionados e de variância constante, além de código por modelo.

## Consequências

- Nenhum dos métodos tem garantia formal: a série temporal e a sobreposição das origens violam a permutabilidade.
- Largura constante no horizonte: premissa apoiada pela estacionariedade da EDA nas diárias e hipótese nas semanais; em passeio aleatório, subcobre nos passos longos.
- Custo: até 64 ajustes extras por fold e no modelo final. É irrelevante nos baselines, mas relevante em SARIMA; `intervalo_max_origens` limita.
- O modelo registrado serve até o horizonte do OOT (14 dias, 2 semanas); acima disso, falha. Versões anteriores ao #8 não têm intervalos.
- **Emenda pós-hoc (D-009):** a soma do erro à previsão produzia limite inferior positivo em séries com muitos zeros e excluía os dias sem venda. Agora, se a fração de zeros do treino for `>= (1 - nível)/2`, o inferior daquele nível é zero, no empírico e no nativo. A regra veio depois de ver a cobertura real, portanto a cobertura do backtest com ela é otimista. Ver `docs/analysis/plano-intervalos.md`, seção 7.
- Com o piso, as diárias atuais têm inferior zero nos dois níveis em todos os folds (28,6% a 50% de zeros). O intervalo vira, na prática, só um limite superior no quantil `1 - (1 - nível)/2`: o de 80% tende a cobrir cerca de 90%. As semanais não têm zeros e não mudam.
