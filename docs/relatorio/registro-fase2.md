# Registro da Fase 2 — treino, backtest e baselines

> Modelo: `_modelo-registro.md`. Exemplo de nível de detalhe: `registro-fase1.md`. Idioma: português. Datas: `AAAA-MM-DD`. Este arquivo separa fato verificado, decisão, hipótese e pendência. As conclusões do #7 foram **APROVADAS pelo usuário (D-006, 2026-10-30)**; hipóteses e interpretações seguem como tais.

## 1. Escopo da fase

Fase 2 (spec `issues/1.md`): primeiro caminho completo de treino. Ticket **#7** (`issues/7.md`): `case-mr-health treinar` para uma série, com backtest de origem móvel, baselines, MAE, MSE, RMSE, WAPE e MASE, previsões truncadas em zero e registro no MLflow. Os candidatos que entram depois (#10 Croston/SBA/TSB; #11 ETS/ARIMA/SARIMA/Prophet), os intervalos (#8) e a confiança (#9) são tickets seguintes; a seleção por série é do #12 e o OOT só é aberto no #13. ADRs: 0002 (backtest e OOT), 0003 (candidatos), 0005 (MLflow), **0006 (novo)**.

## 2. Protocolo e regras vigentes

Herdadas da Fase 1 (`registro-fase1.md`, seção 2): OOT selado até o #13 (o treino só abre a visão de desenvolvimento, via `particoes.abrir_desenvolvimento`); candidatos e hiperparâmetros congelados em `candidatos.py` (D-004), teto de 4 combinações, sem busca de ordem; item C semanal com a semana 07-19 mantida e sensibilidade relatada (decisão 24); sazonal em A e D é hipótese; commits só quando o usuário pedir, sem coautoria do Claude. Política de dados (`.ds-workflow/`): fase `modeling`, D-001 a D-005 aprovadas.

## 3. Linha do tempo por ticket

| Ticket | Branch | Commit(s) | Status | Testes ao final |
| --- | --- | --- | --- | --- |
| #7 Treino de uma série com baselines | `7-treino_baselines` (criada a partir da `main`, que já contém o merge do #6) | nenhum (aguarda pedido do usuário) | `resolved` | 126 (cobertura 98%) |

### 3.1 Ticket #7

**Entregue** (`src/case_mr_health/`):
- `metricas.py`: MAE, MSE, RMSE, WAPE, MASE (escala = MAE do naive de um passo no treino do fold); `nan` quando o denominador é zero.
- `algoritmos.py`: contrato `Previsor` (`ajustar(y)`, `prever(horizonte)`), registro `ALGORITMOS`/`@registrar`, `criar(nome, hiperparametros, seed)`; baselines `naive`, `media_historica`, `naive_sazonal(periodo)`.
- `backtest.py`: `rodar_backtest` (um ajuste por fold só com o treino do fold; previsão truncada em zero; média simples dos folds) e a sensibilidade do item C semanal (`PERIODOS_ATIPICOS`: sem a semana 07-19 e sem os folds 1 e 2).
- `treino.py`: `treinar_serie` (percorre `candidatos()` e treina os que têm implementação, reportando os demais), seed padrão = data local `America/Sao_Paulo` em `YYYYMMDD` (`seed_padrao`), `aplicar_seed` (`random`, `numpy`), registro no MLflow, `ModeloDemanda` (pyfunc; recebe `horizonte`), `hash_artefato`.
- `config.py`: `seed`, `fuso_horario`, `mlflow_tracking_uri` (SQLite local), `mlflow_artifact_dir`. `cli.py`: comando `treinar --sku --granularidade [--seed]`. `.gitignore`: `data/mlflow/`, `mlruns/`.
- Testes: `tests/test_metricas.py`, `test_algoritmos.py`, `test_backtest.py`, `test_treino.py` (séries sintéticas constante, intermitente e sazonal; MLflow temporário em `tmp_path`; sem as planilhas reais). Evidência da execução: `.ds-workflow/test-evidence/test-run-20261030T043914-372445.json` (126 passaram).
- Changelog: `changelogs/7.adicionado.md`. ADR: `docs/adr/0006-treino-por-candidato-e-versao-por-run.md`.

**Critérios de aceite** (`issues/7.md`) e onde conferir: comando com `--seed` opcional (`test_comando_treinar`); partições cronológicas e registradas (`test_run_registra_tags_parametros_e_particoes`); ausência de vazamento, com a alteração do arquivo do OOT sem mudar o backtest (`test_alterar_o_oot_nao_muda_o_backtest`); reprodutibilidade (`test_mesma_seed_reproduz_metricas_e_registra_a_seed`); previsões não negativas (`test_previsoes_sao_truncadas_em_zero`, `test_modelo_registrado_preve_sem_valores_negativos`); métricas conferidas à mão (`test_metricas_conferem_com_o_calculo_a_mao`, `test_naive_em_serie_crescente_confere_com_a_mao`, `test_sensibilidade_do_item_c_semanal_confere_com_a_mao`); nome do modelo por SKU e granularidade (`test_treina_baselines_da_diaria_e_registra_o_modelo_por_sku`); independência entre séries (`test_series_sao_independentes`); filtro por SKU, granularidade e algoritmo (`test_experimentos_filtraveis_por_sku_granularidade_e_algoritmo`).

**Regras e decisões de implementação (do agente; aprovadas em D-006):**
1. Uma **versão do modelo por execução** (candidato × combinação), sem selecionar nada no treino (ADR 0006). Alternativa descartada: registrar só o melhor baseline (exigiria critério de seleção antes do #12).
2. Nome do modelo `demanda-item-a-diaria` (SKU em minúsculas, sem espaço), pois o ADR 0005 não diz como escrever o SKU `item A`.
3. MASE com escala do naive de um passo (m = 1) também na diária. Alternativa: escala de lag 7, hipótese a revisar no #9.
4. Média dos folds simples; métrica indefinida em algum fold fica fora do MLflow e gera a tag `metricas_indefinidas`.
5. Previsão de cada fold com horizonte = tamanho do teste (7 dias ou 1 semana); sem previsão recursiva.
6. SKU aceita `item A` ou `A` na CLI.
7. Config e código: o run grava o `config.json`, a versão do pacote, o commit e se a árvore está suja.

**Fatos verificados.** Execução real, só na visão de desenvolvimento, seed 20261030, `uv run case-mr-health treinar` nas 8 séries (12 runs diários e 8 semanais); números em MLflow (`data/mlflow/mlflow.db`, experimentos `demanda-diaria` e `demanda-semanal`, filtro `params.seed = '20261030'`):

| Série | folds | Naive MAE | Média MAE | Naive sazonal MAE |
| --- | --- | --- | --- | --- |
| A diária | 5 | 2,343 | 2,236 | 2,143 |
| B diária | 4 | 2,143 | 2,538 | 2,536 |
| C diária | 5 | 2,343 | 2,813 | 2,971 |
| D diária | 4 | 2,357 | 2,072 | 3,393 |
| A semanal | 4 | 6,750 | 3,933 | n/a |
| B semanal | 4 | 9,500 | 6,750 | n/a |
| C semanal | 4 | 14,250 | 9,236 | n/a |
| D semanal | 4 | 5,750 | 4,699 | n/a |

Item C semanal (sensibilidade, MAE): naive 14,250 (todas) / 11,667 (sem a semana 07-19) / 6,000 (sem os folds 1 e 2); média 9,236 / 3,536 / 5,090. Desvio-padrão entre folds do MAE: 0,44 a 1,06 nas diárias e 3,5 a 11,9 nas semanais (C: 10,1 e 11,9).

**Observações (o que os números mostram, sem conclusão):**
- WAPE acima de 1 nas diárias B (1,38 a 1,76) e C com média/sazonal (1,11 a 1,19): nos folds, o erro absoluto supera a venda total, comum em séries intermitentes.
- O naive sazonal só teve MAE menor que o naive e a média em A (2,143 contra 2,343 e 2,236). Em B ficou pior que o naive (2,536 contra 2,143) e empatado com a média (2,538); em C e D, pior que ambos. Isto não confirma a hipótese H1 do plano (naive sazonal supera naive e média em B e C) neste backtest de baselines, mas com 4 a 5 folds e desvio-padrão do MAE entre folds de 0,4 a 1,1 a diferença não é distinguível de ruído.
- Na semanal de C, a semana 07-19 pesa muito na média: sem ela, o MAE da média cai de 9,236 para 3,536 e o do naive de 14,250 para 11,667.

**Interpretações (hipóteses, não aprovadas):** o naive sazonal pode estar sendo prejudicado por repetir um único ciclo ruidoso de contagens pequenas (hipótese a verificar com os candidatos sazonais do #11); o desempenho melhor da média na semanal sugere que o nível é estável (hipótese compatível com H4 do plano, a confirmar com os demais candidatos).

**Sinalizações contra ADRs ou spec:** nenhuma contradição. Lacunas do ADR 0005 preenchidas pelo ADR 0006 (nome com SKU, versão por execução).

## 4. Decisões consolidadas

| # | Decisão | Quem | Quando | Justificativa | Onde |
| --- | --- | --- | --- | --- | --- |
| 1 | Itens 1 a 7 da lista de decisões de implementação (seção 3.1) | Agente (proposta), aprovada pelo usuário | 2026-10-30 | Ver seção 3.1 | D-006 (approved), ADR 0006 |
| 2 | Paralelizar as issues seguintes por ondas | Usuário pediu a análise | 2026-10-30 | 20 issues pela frente | `docs/relatorio/plano-paralelizacao.md` (proposta) |

## 5. Questionamentos do usuário e respostas

1. **"Veja se você pode paralelizar as issues para o projeto caminhar mais rápido."** Resposta: sim, em ondas, depois que o #7 estiver integrado; plano e riscos em `docs/relatorio/plano-paralelizacao.md`. Status: proposta, aguarda decisão do usuário.

## 6. Resultados e conclusões

Conclusões **APROVADAS** (D-006, `human_cli`, 2026-10-30): (a) o comando `treinar` e o registro cumprem os critérios de aceite do #7; (b) as decisões de implementação 1 a 7; (c) os números da seção 3.1 são só observações de baselines, sem seleção de modelo.

## 7. Limitações e riscos

- 76 a 79 dias na diária (4 a 5 folds) e 10 semanas na semanal (4 folds): desvio-padrão entre folds comparável às diferenças entre baselines.
- Nenhum candidato além dos baselines foi treinado; o risco de escolha por acaso (11 candidatos) é do #12.
- A semana 07-19 do item C domina o MAE semanal; a sensibilidade fica registrada, mas o critério do #12 deve dizer qual versão usar.
- Várias versões por série acumulam a cada execução; sem política de limpeza.
- Seed: baselines são determinísticos; a seed só fará diferença nos candidatos com aleatoriedade (Prophet).
- O modelo registrado é ajustado só com o desenvolvimento; o retreino com todos os dados após o #13 segue fora do ADR 0002.
- O hash do artefato inclui `uv.lock`/`pyproject.toml` copiados pelo MLflow.

## 8. Referências

- Hyndman, R. J.; Koehler, A. B. (2006). *Another look at measures of forecast accuracy*. International Journal of Forecasting 22(4), 679–688: MASE com escala do naive de um passo. **Não consultado nesta sessão** (citado de memória como referência do método; sem página).
- Documentação do MLflow 3.17.2 (registro de modelos, `pyfunc.log_model`): usada na prática (testes passam), sem localizador de página.

## 9. Pendências e passos de reprodução

- Commit do #7 e demais operações de git só quando o usuário pedir. Onda 1 (#8 a #11) aguarda a troca de modelo e o aviso do usuário.
- Reprodução: `uv sync`; `uv run case-mr-health preparar-dados`; `uv run case-mr-health treinar --sku A --granularidade diaria --seed 20261030`; `uv run poe test`.
