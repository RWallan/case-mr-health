# case-mr-health 0.5.0 (2026-10-30)

## Adicionado

- Explicação em linguagem simples na recomendação (`GET /recomendacoes/{sku}`): campo `explicacao` com `origem` (`llm` ou `template`). Um LLM de qualquer provedor (litellm), com modelo e chave informados pelo usuário nos cabeçalhos `X-LLM-Modelo` e `X-LLM-Chave` ou, na falta deles, pela configuração do servidor, recebe só um contrato estruturado, tem a saída validada por schema e só pode citar números da entrada; sem chave, com falha ou com saída inválida, vale um template determinístico. A decisão continua só da regra. ([#20](issues/20.md))
- Rota `POST /alertas/email` que valida o e-mail do gestor e devolve o conteúdo completo do alerta de um SKU (previsão de 2 semanas, valores, intervalos, recomendação e indicadores) com `envio_simulado: true`; nenhum e-mail é enviado. ([#21](issues/21.md))
- Lista de recomendações por SKU no dashboard, com distinção entre aumento, redução, estável e insuficiente, variação, Q3, aviso, explicação (LLM ou template) e visualização do e-mail de alerta com aviso de envio simulado. ([#23](issues/23.md))
- Dashboard: entrada de previsões por formulário com validação nativa do HTML, upload de XLSX, link do template e tabela de erros do backend com campo e linha. ([#24](issues/24.md))
- Sumário XLSX com aba `Escopo` (completo ou filtrado) e cabeçalho `X-Escopo`, comparação da demanda entre SKUs em um gráfico de linhas e links de Swagger e changelog no cabeçalho do dashboard. ([#25](issues/25.md))

## Interno

- README com instruções de execução do zero ao dashboard, configuração (MLflow remoto, endereços do dashboard) e limitações conhecidas; passada de fumaça do sistema integrado registrada. ([#26](issues/26.md))


# case-mr-health 0.4.0 (2026-10-30)

## Adicionado

- Comando `treinar --todas`, que treina as 8 séries numa mesma rodada, e comando `selecionar`, que aplica o critério pré-registrado no backtest, marca a versão com o alias `selecionado`, grava o gráfico por série no MLflow e gera o resumo. Tarefa `poe test-rapido` e marcador `lento` para separar os testes que treinam modelos. ([#12](issues/12.md))
- Adicionados os comandos `avaliar-final`, que abre o OOT uma única vez e registra métricas e cobertura das 8 versões selecionadas, e `promover`, que atribui o alias `champion` a uma versão avaliada com decisão de publicação aprovada. ([#13](issues/13.md))
- API de predição individual (`POST /predicoes`) e comando `case-mr-health servir`: carrega na inicialização a versão `champion` ou fixada (`modelos_fixados`) de cada SKU e granularidade, confere o hash do artefato, nunca treina e responde a previsão da rede por período-alvo, com quantidade, valor, limites de 80% e 95%, versão, hash, experimento e confiança opcional. Série sem modelo fica indisponível sem derrubar a API; mensal, data inválida e horizonte além do máximo validado são rejeitados com justificativa. Cada período servido é gravado no histórico em DuckDB exclusivo do serviço (`historico_db_path`), com um único worker. Swagger com descrições, exemplos e erros. ([#14](issues/14.md))
- Adicionadas a predição em lote (JSON e XLSX) e o template XLSX, com validação tudo ou nada e erros por item, linha e coluna. ([#15](issues/15.md))
- Adicionadas consultas paginadas do histórico de previsões, catálogo de versões do MLflow e exportação do histórico para XLSX. ([#16](issues/16.md))
- Rota `GET /changelog` com o changelog estruturado do projeto: versões na ordem do arquivo, data e mudanças por tipo, cada uma com o texto e os IDs das issues ligadas, extraídas do `CHANGELOG.md` do towncrier (caminho em `Settings.changelog_path`). Changelog ausente ou vazio responde 200 com `versoes` vazia, e conteúdo fora do formato é ignorado com aviso no log. ([#17](issues/17.md))
- Adicionada a rota `GET /recomendacoes/{sku}`, que recomenda aumento significativo, redução significativa, estável ou insuficiente pela regra determinística do modelo semanal (4 semanas vendidas contra 2 previstas, limite no Q3 histórico), sempre com o aviso de baixa confiabilidade estatística. ([#19](issues/19.md))
- Adicionado dashboard Svelte para consultar o histórico de desenvolvimento e visualizar previsões da rede com intervalos de 80% e 95%. ([#22](issues/22.md))
- Removida a classificação de confiança dos modelos, da API e do histórico de previsões após a validação mostrar baixa utilidade nas séries disponíveis. ([#27](issues/27.md)) ([#27](issues/27.md))
- Adicionada a ingestão de pedidos novos (planilhas de pedidos e itens) na base, com validação por planilha e linha, hash dos dados e reconstrução das séries. ([#28](issues/28.md))
- Adicionado o reajuste do modelo servido na série estendida, que registra uma nova versão com o mesmo algoritmo e hiperparâmetros e rastreabilidade dos dados. ([#29](issues/29.md))
- Adicionadas as rotas `POST /dados/pedidos` e `GET /dados/atualizacoes/{id}`, que ingerem pedidos novos e reajustam os modelos em segundo plano, e o comando `reajustar`; a API passa a informar a origem do modelo. ([#30](issues/30.md))
- Adicionado ao dashboard o envio de pedidos novos, com erros por planilha e linha, acompanhamento do reajuste e atualização do gráfico. ([#31](issues/31.md))

## Correções

- Corrigido o `GET /modelos`, que não mostrava o alias `champion` com o MLflow real. ([#30](issues/30.md))

## Alterado

- Removido da especificação o campo `quantidade` da predição em batch (#15): o contrato da predição individual não muda. ([#15](issues/15.md))
- A exportação XLSX e a consulta de previsões ganharam a coluna/campo `recomendacao`, gravada no histórico pelas chamadas de `GET /recomendacoes/{sku}`; bancos de histórico antigos são migrados na abertura. ([#19](issues/19.md))

## Interno

- Especificação detalhada da regra de recomendação aprovada, com casos de exemplo para o #19. ([#18](issues/18.md))
- Proposto o ADR 0011 e abertos os tickets #28 a #31 para ingestão de pedidos novos e reajuste do modelo pela API.


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
