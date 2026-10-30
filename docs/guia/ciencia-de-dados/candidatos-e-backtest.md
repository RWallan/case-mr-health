# Candidatos e backtest

## O que é um candidato

Cada série (SKU e granularidade) tem uma **tabela de candidatos**, definida em `candidatos.py` (`candidatos()` em `candidatos.py:418`; `tabela()` achata as 8 séries). A tabela não treina nada: ela diz quem entra no backtest, com as premissas do método, a **base** da decisão e o espaço de hiperparâmetros. A base é rotulada como `evidencia`, `hipotese`, `decisao_usuario`, `aritmetica` ou `regra` (`candidatos.py:19-23`), o que separa o que um teste mostrou do que foi suposto ou decidido por uma pessoa.

Um candidato é uma classe com `ajustar(y)` e `prever(horizonte)` (contrato `Previsor`, `algoritmos.py:17`), registrada em `ALGORITMOS`. O fluxo de treino e de backtest só conhece esse contrato (ADR 0006, [texto](../decisoes/adr/0006-treino-por-candidato-e-versao-por-run.md)). Todo ajuste recebe apenas o treino do fold, em ordem cronológica.

## Quem entra, por série

O quadro abaixo vem de `candidatos.py` (funções `_baselines:134`, `_ets_arima:202`, `_intermitentes:335` e `_prophet:387`), no estado do código em 2026-10-30. "Entra" quer dizer `entra = True` na tabela.

| Candidato | Diária | Semanal | Origem da decisão |
| --- | --- | --- | --- |
| `naive` (baseline) | entra | entra | regra: baseline obrigatório (ADR 0003) |
| `media_historica` (baseline) | entra | entra | regra: baseline obrigatório (ADR 0003) |
| `naive_sazonal` (baseline, lag 7) | entra | **não entra** | diária: base `evidencia` se a sazonalidade foi confirmada (B, C), `hipotese` nas inconclusivas (A, D); semanal: aritmética, sem sazonalidade testável em 10 semanas |
| `ets_ses` | entra | entra | regra |
| `ets_holt_winters_aditivo` (período 7, sem tendência) | entra | não entra | diária: conforme a sazonalidade; semanal: ausente da tabela |
| `ets_holt_amortecido` | não existe | **não entra** | decisão do usuário, corte de 2026-10-30 (`candidatos.py:276`; arima diária `:243`, semanal `:296`; prophet `:402`) |
| `arima` | **não entra** | **não entra** | decisão do usuário, corte de 2026-10-30 |
| `sarima` (AR sazonal 1, período 7) | entra | **não entra** | diária: ordem fixa `(0,0,0)` e sazonal `(1,0,0,7)`; semanal: aritmética (ciclo de 4 ou 52 semanas não cabe em 10 pontos) |
| `croston`, `sba`, `tsb` | entram | **não entram** | diária: série intermitente (evidência); semanal: série suave (ADI = 1, sem zeros em 10 semanas) |
| `prophet` | **não entra** | **não entra** | decisão do usuário, corte de 2026-10-30 |

!!! warning "Desvio entre ADR e código"
    O ADR 0003 (`docs/adr/0003-candidatos-de-algoritmo.md`) e o ADR 0010 (`docs/adr/0010-falha-de-convergencia-e-calendario-sintetico-do-prophet.md`) descrevem ARIMA e Prophet como candidatos. O código atual os marca como excluídos, com o motivo "Corte de 2026-10-30, decisão do usuário (emenda a D-004)" (`candidatos.py`, campo `motivo` de `arima`, `ets_holt_amortecido` e `prophet`). Não encontrei um ADR que registre esse corte; a decisão D-004 e a emenda estão citadas só no código. **A implementação do Prophet e do ARIMA continua no repositório**, apenas fora da tabela. O registro MLflow é coerente com o corte: os `selecionado` das diárias são `naive_sazonal`, `tsb`, `media_historica` e `sarima` (ver [Seleção](selecao-e-intervalos.md)). Isto foi verificado nas tags `algoritmo` das versões, e não no log de decisões, que não foi lido.

Pontos conceituais que o quadro mostra:

- **Baselines primeiro.** `naive`, `media_historica` e, na diária, `naive_sazonal` são o piso de comparação. Um método sofisticado só vale se ganhar deles (regra de seleção, ver adiante).
- **Os intermitentes são de demanda, não de série temporal genérica.** Croston, SBA (Syntetos e Boylan) e TSB (Teunter, Syntetos e Babai) estimam separadamente o tamanho da venda e a probabilidade de haver venda; a previsão é constante, sem dia da semana. Entraram porque 33% a 46% dos dias das séries diárias não têm venda (ADR 0003). Foram implementados em código próprio para evitar `numba` e `statsforecast` no Python 3.14 (ADR 0003; `algoritmos_intermitentes.py`).
- **Premissas são verificadas, não impostas.** Cada `ajustar` confere as premissas do método com o próprio treino e grava o resultado em `diagnosticos.json` e nas tags `premissas_nao_atendidas` e `premissas_nao_testaveis`. Premissa não atendida **não** tira a combinação do treino; o que fazer com ela é decisão da seleção (ADR 0010).
- **Falha de convergência invalida a combinação inteira.** Se um fold, ou o ajuste final, falhar, o run vira `FAILED` e a combinação sai da comparação, em vez de comparar médias sobre folds diferentes (ADR 0010; a seleção só lê `status = 'FINISHED'`, `selecao.py:176`).

## Hiperparâmetros

O espaço de cada candidato é o produto cartesiano de listas pequenas (`Candidato.combinacoes`, `candidatos.py:89`). Valores no código atual:

| Candidato (diária) | Espaço | Fonte |
| --- | --- | --- |
| `naive_sazonal` | `periodo = 7` | `_baselines` |
| `ets_ses` | `alfa` estimado pelo ajuste | `_ets_arima` |
| `ets_holt_winters_aditivo` | `periodo = 7`, `tendencia = nenhuma` | `_ets_arima` |
| `sarima` | `ordem = (0,0,0)`, `ordem_sazonal = (1,0,0,7)`, com constante | `_ets_arima` |
| `croston`, `sba` | `alfa` em 0,1; 0,2; 0,3 | `_intermitentes` |
| `tsb` | `alfa_beta` em 0,1; 0,2; 0,3 (α = β) | `_intermitentes` |

A tabela semanal só tem `media_historica`, `naive` e `ets_ses` (sem hiperparâmetro). Os espaços são pequenos e há uma constante `MAX_COMBINACOES = 4` (`candidatos.py:17`). **Hipótese** (não documentada em ADR): a razão seria evitar que, com ~80 dias de treino por série, uma grade grande ajustasse a escolha aos folds; nenhum experimento do repositório lido compara grades maiores.

!!! note "Valores selecionados"
    Hiperparâmetros das versões escolhidas, lidos da tag `hiperparametros` no registro: item B diária `tsb` com `alfa_beta = 0,2`; item D diária `sarima` com `ordem = [0,0,0]` e `ordem_sazonal = [1,0,0,7]`; item A diária `naive_sazonal` com `periodo = 7`; item C diária e as quatro semanais, `media_historica` sem hiperparâmetro.

## Backtest de origem móvel

`rodar_backtest` (`backtest.py:63`) recebe só a visão de desenvolvimento. Para cada fold da partição:

1. recorta o treino (`treino_inicio` a `treino_fim`) e o teste;
2. instancia um previsor novo, ajusta **só com o treino do fold** e prevê o horizonte do teste;
3. **trunca a previsão em zero** (`np.clip`, `backtest.py:90`), porque venda não é negativa;
4. calcula as métricas do fold e, se pedido, a cobertura dos intervalos (calibrados também só com o treino do fold).

A métrica de teste do candidato é a **média simples** das métricas dos folds (`media_dos_folds`, `backtest.py:54`). Se uma métrica é indefinida em algum fold, a média é indefinida e a execução recebe a tag `metricas_indefinidas` (ADR 0006).

**Sensibilidade.** Para séries com período atípico declarado, o backtest também relata as médias sem esse período e sem os 2 primeiros folds (`backtest.py:164`, `FOLDS_INICIAIS_EXCLUIDOS = 2`). Hoje há um só período declarado: item C semanal, semana de 2021-07-19 (`backtest.py:27-29`), mantido na série por decisão do usuário (decisão 24 do registro da Fase 1, citada no comentário do código; `docs/relatorio/registro-fase1.md` não foi relido para esta página).

## Métricas

Cinco métricas por fold (`metricas.py:10`, `METRICAS`):

| Métrica | Definição | Quando é indefinida | Fonte |
| --- | --- | --- | --- |
| MAE | média do erro absoluto | nunca (exige fold não vazio) | `metricas.py:13` |
| MSE | média do erro ao quadrado | nunca | `metricas.py:17` |
| RMSE | raiz do MSE | nunca | `metricas.py:21` |
| WAPE | soma do erro absoluto ÷ soma do observado | fold sem venda (soma zero) | `metricas.py:25` |
| MASE | MAE do fold ÷ MAE do naive de um passo **no treino do fold** | escala zero | `metricas.py:33-44` |

Pontos que evitam leitura errada:

- **WAPE acima de 1** acontece: o erro total supera o volume vendido no fold. Na avaliação final, por exemplo, item A diária tem WAPE 1,129 no OOT (`docs/relatorio/fase4/13-avaliacao-final.md`, citado, não recalculado).
- **MASE abaixo de 1 não significa ganhar do baseline.** A escala é o erro do naive de um passo dentro do treino, não o erro de um baseline no mesmo teste (ADR 0008, Consequências). Em série diária com ciclo semanal, a escala de lag 7 seria uma alternativa; o ADR 0006 e o 0008 deixam essa troca como decisão do usuário, e ela não foi feita.
- **MASE do OOT e do backtest não são comparáveis diretamente.** O do OOT usa a escala do naive de todo o desenvolvimento; o do backtest usa a de cada treino de fold (`13-avaliacao-final.md`, parágrafo de abertura).
- **Quem decide a seleção é o MAE**, com RMSE, viés e sensibilidade como sinais (`selecao.py:154`). Ver a próxima página.

## Fontes e limites desta página

Lidos: `candidatos.py`, `algoritmos.py`, `backtest.py`, `metricas.py`, ADRs 0003, 0006, 0008 e 0010. Não lidos: `plano-candidatos.md` (congelado antes dos resultados e citado pelo código), os módulos de `algoritmos_statsmodels.py` e `algoritmos_prophet.py` além de buscas pontuais, e os resultados por candidato fora do que está em `docs/relatorio/fase2/12-resumo.md`.
