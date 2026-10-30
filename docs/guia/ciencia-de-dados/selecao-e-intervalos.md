# Seleção e intervalos

## Seleção: só pelo backtest, com freio

A seleção (`selecao.py`) escolhe uma versão por série **usando apenas o backtest**. O OOT não entra. O critério foi fixado antes de qualquer resultado de candidato, em `docs/relatorio/fase2/12-pre-registro.md` (citado pelo docstring de `selecao.py:1`; o pré-registro não foi relido para esta página).

A regra, como implementada em `selecionar` (`selecao.py:124`):

1. Descartam-se as versões sem intervalo servível (`intervalo_metodo = indisponivel`, `elegiveis`, `selecao.py:109`).
2. O **melhor baseline** da série é a referência: menor MAE médio dos folds; empate (tolerância `1e-9`) vai para o mais simples, na ordem de `ORDEM_SIMPLICIDADE` (`selecao.py:28`).
3. Cada candidato (não baseline) é comparado ao baseline **de forma pareada**, fold a fold: `d = MAE_baseline − MAE_candidato`. Ele só "supera" se a média de `d` for positiva **e** maior que o erro-padrão dessa média (`selecao.py:87-93` e `:136`, `supera = media > 0 and media > ep`).
4. Entre os que superam, vence o de menor MAE; se nenhum supera, o vencedor é o próprio baseline (`selecao.py:137`).
5. Sinais de aviso (menor RMSE em outro candidato, viés relativo acima de 20%, melhor outro candidato sem o período atípico ou sem os 2 primeiros folds) são gravados, mas **não mudam o vencedor** (`_sinais`, `selecao.py:154`; `LIMITE_VIES_RELATIVO = 0.20`).

O comentário do código explica o que isso é: "com 4 a 5 folds isso é um freio contra a escolha por acaso, não prova de superioridade" (`selecao.py:5-7`). Um erro-padrão com 5 folds é uma barra baixa; ela só impede ganhos que nem sequer apareceram na média.

**Desvio do pré-registro.** O `naive` diário foi tirado da disputa depois de ver os resultados e antes de abrir o OOT, com aprovação do usuário, porque em série intermitente ele repete o último dia por todo o horizonte (no item B isso daria zero por 14 dias) (`FORA_POS_HOC`, `selecao.py:42`, comentário). É uma regra pós-hoc e o relatório precisa lembrá-la.

O resultado da seleção é o alias `selecionado` na versão vencedora (`_marcar`, `selecao.py:241`). Ele **não** é o modelo servido: o servido é o `champion`, atribuído na publicação (ver [Reajuste e avaliação final](reajuste-e-avaliacao.md)).

### Resultado, citado do relatório da Fase 2

Fonte: `docs/relatorio/fase2/12-resumo.md` (rodada `3051af2281b74935981b7ccf6d98e7f8`). Os números são do backtest e foram copiados, não recalculados. A coluna de confiança do original foi omitida (ver adiante).

| Série | Vencedor | Baseline de referência | MAE | MAE do baseline | d̄ | ep | MASE | Cobertura 80% / 95% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| item A diária | `naive_sazonal` (período 7) | `naive_sazonal` | 2,143 | 2,143 | +0,000 | 0,000 | 0,811 | 1,00 / 1,00 |
| item A semanal | `media_historica` | `media_historica` | 3,933 | 3,933 | +0,000 | 0,000 | 0,664 | 0,75 / 1,00 |
| item B diária | `tsb` (alfa_beta 0,2) | `naive_sazonal` | 2,369 | 2,536 | +0,167 | 0,089 | 0,821 | 0,89 / 0,93 |
| item B semanal | `media_historica` | `media_historica` | 6,750 | 6,750 | +0,000 | 0,000 | 0,605 | 1,00 / 1,00 |
| item C diária | `media_historica` | `media_historica` | 2,813 | 2,813 | +0,000 | 0,000 | 1,005 | 0,83 / 1,00 |
| item C semanal | `media_historica` | `media_historica` | 9,236 | 9,236 | +0,000 | 0,000 | 1,877 | 0,50 / 0,75 |
| item D diária | `sarima` (0,0,0)(1,0,0,7) | `media_historica` | 2,033 | 2,072 | +0,040 | 0,020 | 0,682 | 0,93 / 0,93 |
| item D semanal | `media_historica` | `media_historica` | 4,699 | 4,699 | +0,000 | 0,000 | 0,963 | 0,75 / 1,00 |

O que a tabela sustenta, separado do que não sustenta:

- **Evidência.** Em 6 das 8 séries o vencedor é um baseline (`d̄ = 0`); só item B diária (`tsb`) e item D diária (`sarima`) superaram o baseline de referência pelo critério.
- **Evidência.** Nas semanais, todas as escolhidas são `media_historica`; só ela e `naive`/`ets_ses` entram na tabela semanal (ver [Candidatos](candidatos-e-backtest.md)).
- **Hipótese.** Que `tsb` e `sarima` sejam melhores que o baseline além da amostra. O ganho do item D é de 0,040 contra um erro-padrão de 0,020 (valores arredondados do relatório), com 5 folds e sem correção para a comparação de vários candidatos. Não foi verificada estabilidade fora desses folds.
- **Cuidado.** `MASE` do item C semanal (1,877) é maior que 1: a média histórica erra mais, em escala de naive de um passo, do que o naive no treino. A regra compara candidatos entre si e não impõe um teto de MASE. O período atípico dessa série (2021-07-19) está sob sensibilidade no backtest.

## Intervalos de previsão

Todo modelo servido responde com intervalos de **80% e 95%** (`niveis_intervalo`, `config.py`). A regra está no ADR 0007 ([texto](../decisoes/adr/0007-intervalos-empiricos-por-origem-movel.md), status aprovado pelo usuário em 2026-10-30) e em `intervalos.py`.

### Mecanismo empírico

Usa só `ajustar` e `prever`, logo funciona para qualquer previsor. Dentro do treino, cada origem móvel prevê de uma vez `h` períodos (até o horizonte do OOT: 14 dias ou 2 semanas); os erros de 1 a `h` passos, **agrupados**, formam os limites (`calibrar`, `intervalos.py:178`).

| Situação | Método | Tag `intervalo_metodo` | Fonte |
| --- | --- | --- | --- |
| Erros suficientes: 39 para 95% (`minimo_de_erros`, `intervalos.py:157`) | quantis assimétricos | `empirico_quantil` | ADR 0007; `intervalos.py:178-205` |
| Poucos erros, mas pelo menos 2 origens | intervalo de predição t de Student | `empirico_t` | `ORIGENS_MINIMAS = 2`, `intervalos.py:36` |
| Menos de 2 origens válidas | sem intervalo; a versão não é servível | `indisponivel` | `intervalos.py:200-205` |
| Intervalo nativo do modelo | usado só se passar pela regra de calibração | `nativo` | `decidir_nativo`, `intervalos.py:301` |

A regra do nativo foi fixada antes de olhar a cobertura real: disponível, `n >= 20` (para 95%), o nível nominal dentro do intervalo de Wilson e subcobertura de no máximo 5 pontos (`TOLERANCIA_SUBCOBERTURA`, `intervalos.py:37`). Na semanal, com 4 pontos de teste, o nativo nunca é usado (ADR 0007).

No registro MLflow, as tags `intervalo_metodo` das versões `selecionado` são: `empirico_quantil` para item A, B e C diárias, **`nativo` para item D diária** (o `sarima`) e `empirico_t` para as quatro semanais.

### Piso zero (emenda D-009, pós-hoc)

Se a fração de zeros do treino for maior ou igual a `(1 − nível)/2`, o limite inferior daquele nível é zero (`tem_piso_zero`, `intervalos.py`). O ADR 0007 registra que **a regra veio depois de ver a cobertura real**, portanto a cobertura do backtest com ela é otimista. Nas diárias atuais, o inferior é zero nos dois níveis em todos os folds (28,6% a 50% de zeros): o intervalo vira, na prática, só um limite superior.

### Limites que a documentação assume

- Nenhum método tem garantia formal de cobertura: a série temporal e a sobreposição das origens violam a permutabilidade (ADR 0007).
- Largura constante no horizonte: apoiada pela estacionariedade da EDA nas diárias e **hipótese** nas semanais (ADR 0007).
- O modelo registrado serve até o horizonte do OOT (14 dias ou 2 semanas); acima disso, falha (`Calibracao.limites`, `intervalos.py`).
- A cobertura no OOT da avaliação final (1,000 em vários casos) tem granularidade de 1/14 na diária e de 1/2 na semanal; ver `docs/relatorio/fase4/13-avaliacao-final.md`.

## Confiança pelo MASE: removida

O ADR 0008 definia uma "confiança" por versão (Ótima, Boa, Média, Ruim ou Insuficiente), derivada do MASE do backtest. **Ela não faz mais parte da solução.**

**O que se verifica no código (leitura de 2026-10-30):**

- Não existe módulo de confiança em `src/case_mr_health/` (a listagem do diretório não tem `confianca*.py`) e `config.py` não tem `confianca_limites`, `confianca_nivel_ic` nem `confianca_max_fronteiras_ic`.
- `recomendacao.py:6` diz que "a confiança do modelo não entra (D-020)"; `api/rotas/consultas.py:106` e `api/servicos/consultas.py:62` dizem que a coluna removida não é exportada; `api/rotas/alertas.py:63`, que o alerta não tem confiança por previsão; `avaliacao_final.py:337` repete "sem confiança de modelo".
- Não há ocorrência de `confianca` em `frontend/src` nem em `api/` além desses comentários.
- Resta um campo opcional `confianca: float | None` em `explicacao.py:96`, usado só para montar a explicação por LLM se alguém o informar. Não verifiquei se algum chamador o preenche; **pendência de limpeza possível**, fora do escopo desta página.

**O que se verifica no registro MLflow (leitura, sem escrita):** 72 das 100 versões registradas ainda têm as tags históricas `confianca*` (576 linhas de tag); as 8 versões de reajuste, não. É resíduo de dados, não de comportamento: nada no código lido as consulta. Isso é consistente com o ADR 0008, que diz que o notebook de validação e os registros da fase permanecem como evidência histórica.

**Por que foi removida (ADR 0008, seção "Revisão", D-020):** na validação repetida no #12, só 2 dos 8 modelos selecionados saíram de Insuficiente; os critérios I1 e I3 do pré-registro dispararam; 45 dos 72 runs e todos os 12 semanais ficaram Insuficiente; a alternativa pareada também falhou nos baselines (2 de 12 pares, mínimo de 3). O usuário decidiu removê-la; a remoção foi feita no #27. Fonte do registro da decisão: `docs/relatorio/registro-fase2.md`, linha 11 da tabela de decisões. O ADR 0008 está marcado "substituído em 2026-10-30" no próprio texto.

!!! info "Ainda vale a lição"
    O motivo da remoção é estatístico: com 4 a 5 folds, a média do MASE é tão incerta que as faixas não discriminam. Isso é também um limite desta documentação; nenhuma faixa de "boa" ou "ruim" por MASE deve ser inferida dos números aqui citados.

## Fontes e limites desta página

Lidos: `selecao.py`, `intervalos.py` (trechos), `config.py`, `docs/relatorio/fase2/12-resumo.md`, ADRs 0007 e 0008, `docs/relatorio/registro-fase2.md` (linha da decisão) e as tags do registro MLflow, via leitura SQLite do arquivo `data/mlflow/mlflow.db`. Não lidos: `docs/relatorio/fase2/12-pre-registro.md`, `plano-intervalos.md`, o notebook `04_validacao_confianca.ipynb` e `.ds-workflow/decisions.jsonl` (D-009, D-019, D-020 citadas pelo ADR e pelo registro da fase, não conferidas na fonte).
