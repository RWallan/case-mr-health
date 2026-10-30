# case-mr-health 0.3.0 (2026-10-30)

## Adicionado

- Comando `case-mr-health treinar --sku --granularidade [--seed]`: backtest de origem móvel na visão de desenvolvimento, baselines (naive, média histórica e naive sazonal), MAE, MSE, RMSE, WAPE e MASE por fold e na média, previsões truncadas em zero, sensibilidade do item C semanal (sem a semana 07-19 e sem os folds 1 e 2) e registro no MLflow (um experimento por granularidade, tags `sku`, `granularidade` e `algoritmo`, modelo `demanda-<sku>-<granularidade>` com hash do artefato). Interface `Previsor` e `registrar` para plugar candidatos novos sem mudar o fluxo. ([#7](issues/7.md))
- Intervalos de previsão de 80% e 95% para todo modelo treinado (`intervalos.py`): mecanismo empírico por origem móvel dentro do treino, que serve a qualquer `Previsor`, e intervalo nativo opcional usado só se calibrado. Limites não negativos, aninhados e contendo a previsão, com piso zero no limite inferior quando a fração de zeros do treino é de ao menos `(1 - nível)/2` (D-009). Cobertura do backtest, método e motivo registrados no MLflow; o modelo registrado expõe os limites com a coluna `intervalos` no `predict`. Níveis em `Settings.niveis_intervalo`. ([#8](issues/8.md))
- Confiança de cada versão do modelo, calculada no backtest a partir do MASE, com faixas configuráveis (Ótima, Boa, Média e Ruim) e o status Insuficiente para MASE indefinido, folds de menos ou MASE instável. Os valores vão como tags da versão e do run no MLflow. Notebook `04_validacao_confianca.ipynb` com a validação das faixas nas 8 séries. ([#9](issues/9.md))
- Croston, SBA e TSB como candidatos do comando `treinar` nas séries diárias, com implementação própria, sem `numba` nem `statsforecast`, previsão constante e não negativa, e cada combinação de suavização registrada no MLflow. ([#10](issues/10.md))
- Candidatos ETS (SES, Holt-Winters aditivo e Holt amortecido), ARIMA, SARIMA e Prophet (só sazonalidade semanal) no comando `treinar`, com intervalos nativos, premissas verificadas no treino de cada fold (`diagnosticos.json` e tags no MLflow) e falhas de convergência registradas como runs `FAILED`, sem interromper o treino. O modelo registrado declara as dependências do previsor com as versões instaladas. ([#11](issues/11.md))

## Alterado

- Corta da tabela ARIMA diário e semanal, Holt amortecido semanal e Prophet, e reduz o SARIMA diário a uma combinação, por decisão do usuário (D-007). ([#11](issues/11.md))
- Simplifica o escopo do frontend: página única em Svelte com Vite, sem testes de componentes nem Playwright, e com link para a UI do MLflow.


# case-mr-health 0.2.0 (2026-10-30)

## Adicionado

- Comando `case-mr-health preparar-dados`, que consolida as planilhas brutas em DuckDB (pedido, item de pedido e SKU) e gera o relatório de qualidade; configuração com pydantic-settings, logs com loguru e CLI com cyclopts; notebook de EDA por fonte e de relacionamento; planilhas brutas versionadas em `data/raw/`. ([#2](issues/2.md))
- O `preparar-dados` passa a gerar as séries diária e semanal por SKU (calendário do SKU, zeros imputados marcados, semanas de segunda a domingo apenas completas); notebook ganha a seção sobre os 12 dias sem pedido na rede. ([#3](issues/3.md))
- Partições por série (OOT final e folds de origem móvel com janela expansiva, tamanhos configuráveis), com a visão de desenvolvimento e o OOT gravados em arquivos DuckDB separados; treino mínimo da série diária de 42 dias. ([#4](issues/4.md))
- Diagnósticos de séries curtas e intermitentes (zeros, ADI/CV², autocorrelação, estacionariedade, sazonalidade por dia da semana, razão fim de semana e outliers) e notebook de EDA das séries na visão de desenvolvimento, com confronto aos números da Fase 0; `statsmodels` e `prophet` adicionados após verificar compatibilidade com o Python 3.14. O ADR 0003 foi corrigido com a faixa de zeros medida na visão de desenvolvimento. ([#5](issues/5.md))
- Tabela de candidatos de algoritmo por série (módulo `candidatos` e notebook `03_candidatos`): para as 8 séries, quem entra, premissas, base (evidência ou hipótese) e espaço de hiperparâmetros com teto de 4 combinações. Nenhum modelo é treinado. ([#6](issues/6.md))

## Interno

- Especificação do sistema de previsão de demanda (Fase 0), glossário de domínio e ADRs 0001 a 0005. ([#1](issues/1.md))
- Configuração das skills de agente (issue tracker local, labels de triage e docs de domínio) em `docs/agents/`.
- Decisões do usuário sobre pares repetidos, dias sem pedido, preço por unidade e item C registradas no registro da Fase 1, nos notebooks, na spec e no ticket #7; modelo de registro por fase em `docs/relatorio/_modelo-registro.md`.
- Quebra da spec em tickets de implementação (#2 a #26) por fase, com bloqueios entre eles.
- Registro da Fase 1 (decisões, evidências, questionamentos e pendências) em `docs/relatorio/registro-fase1.md`, base para o relatório final.
- Texto de continuação para o ticket #6 em `docs/relatorio/continuacao-6.md`.
