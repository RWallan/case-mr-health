# Continuação: ticket #6 (tabela de candidatos por série)

Texto pronto para colar numa nova sessão do Claude Code, na raiz do repositório. Ele vale para um agente **sem o contexto da conversa anterior**. O agente deve invocar a skill `evidence-based-data-science-workflow` (`/evidence-based-data-science-workflow`) e usar este texto como argumento.

---

## Prompt para colar

Vamos executar o ticket #6 da Fase 1 do projeto MR. HEALTH (spec em `issues/1.md`, ticket em `issues/6.md`): a **tabela de candidatos de algoritmo por série**. O #6 fecha a Fase 1. Os tickets #2 a #5 já estão resolvidos e aprovados por mim. **Não treine nem ajuste modelos**: o treino começa no #7.

### 1. Leia antes de tudo (nesta ordem)
1. `CLAUDE.md`, `GLOSSARY.md`, `docs/adr/0001` a `0005`.
2. **`docs/relatorio/registro-fase1.md`**: o registro completo do que foi feito, dos números, das decisões e dos meus questionamentos. É a fonte principal de contexto.
3. `issues/1.md` (spec), `issues/6.md` (o ticket; os critérios de aceite são o contrato) e `issues/4.md` e `issues/5.md` (seção "Answer").
4. `notebooks/02_eda_series.ipynb` (resultados da EDA já aprovados) e `src/case_mr_health/diagnosticos.py`, `particoes.py`.
5. `.ds-workflow/` (`ds_policy.py status` e `decisions`): a política de dados e as decisões D-001 e D-002 (aprovadas). A fase atual é `awaiting_user_direction`.

### 2. Regras que valem para toda a Fase 1 (não renegocie)
- **O período OOT está selado.** Use somente a visão de desenvolvimento, aberta com `case_mr_health.particoes.abrir_desenvolvimento` (ou `carregar_particoes` para as datas). Nenhuma célula ou comando lê o OOT, nem o arquivo da base completa, até o ticket #13. Os nomes desses arquivos estão em `src/case_mr_health/config.py`.
- O hook da skill bloqueia comandos e **escritas de arquivo que citam os nomes dos arquivos selados** (inclusive em documentação). Não contorne: refira-se a eles de forma genérica ("o arquivo do OOT") e aponte para `config.py` e `.ds-workflow/data-policy.json`. Se algo for negado, explique a negativa a mim.
- Visão de desenvolvimento: diária com 79 dias (A, C) e 76 dias (B, D); semanal com 10 semanas completas (06-07 a 08-15). Folds e treino mínimo (42 dias na diária; 6 semanas na semanal) já estão nas tabelas `particao` e `fold` da visão de desenvolvimento.
- **Opção A (vazamento entre granularidades):** a visão diária contém 08-16 a 08-18, dias que pertencem ao OOT semanal. Decisões sobre a série semanal usam somente a visão semanal.
- Separe sempre **evidência** (resultado de teste do #5, com número) de **hipótese**. Sazonalidade, estacionariedade e intermitência só são afirmadas com teste formal, premissas checadas e referência com página. Deixe explícitas as limitações de amostra.
- **Conclusões e decisões vão para a minha aprovação antes de serem registradas** no notebook ou no ticket. Silêncio não é aprovação. A aprovação formal é registrada por mim com `! python3 ~/.claude/skills/evidence-based-data-science-workflow/scripts/ds_policy.py approve D-xxx`; você não pode rodar `approve`.
- Se algo contradisser um ADR, sinalize explicitamente; não sobrescreva em silêncio.
- Engenharia (`CLAUDE.md`): pacote em `src/case_mr_health/`, DuckDB, pydantic-settings, loguru (sem `print`), cyclopts, testes pytest com fixtures e `faker` sem depender das planilhas reais, ruff com aspas simples e linha de 79 (`uv run poe format` e `uv run poe test` antes de concluir), fragmento towncrier `changelogs/6.adicionado.md`, **commits sem coautoria do Claude**, ticket com `Status: resolved` ao terminar. Crie a branch `6-tabela_candidatos` a partir de `5-eda_series` e marque o #6 como `claimed` antes de começar.
- Atualize `docs/relatorio/registro-fase1.md` ao final (decisões, evidências, perguntas minhas, limitações e pendências), porque o relatório final do projeto será escrito a partir dele.

### 3. O que o #6 pede
Para **cada uma das 8 séries** (4 SKUs × diária e semanal), uma tabela de candidatos que informe:
- se o candidato entra ou não, e por quê;
- as premissas que ele exige e se a EDA do #5 mostrou que elas são atendidas;
- o que é **evidência** (teste do #5) e o que é **hipótese**;
- os **baselines** de cada série;
- o **espaço de hiperparâmetros**, propositalmente pequeno, para evitar sobreajuste em séries curtas (história 53 da spec).

Universo de candidatos (ADR 0003): baselines (naive, média histórica e naive sazonal quando houver evidência de sazonalidade), ARIMA/SARIMA/ETS via `statsmodels`, Croston, SBA e TSB em implementação própria, e Prophet. O ARIMA_PLUS fica fora. Eu decidi **manter a série diária** para testar os métodos intermitentes. O `statsmodels` (0.15.0) e o `prophet` (1.5.0) já estão instalados e funcionam no Python 3.14, então o Prophet é candidato, a ser avaliado série a série.

Entregáveis: tabela por série no notebook (novo, por exemplo `notebooks/03_candidatos.ipynb`, lendo só a visão de desenvolvimento), e em formato consumível pelo treino se for útil (por exemplo, um módulo ou arquivo de configuração versionado); testes; fragmento towncrier; **apresentação de encerramento da Fase 1** (o que foi feito, testes, decisões, limitações e conclusões), com sugestão de versão (Semantic Versioning) para o `towncrier build`.

### 4. Evidência já disponível do #5 (visão de desenvolvimento)
Use como ponto de partida e confirme no notebook; números completos em `registro-fase1.md`, seção 3.4.
- **Zeros na diária:** A 43,0%, B 36,8%, C 45,6%, D 32,9%. Semanal: 0/10 em todos os SKUs.
- **Intermitência (classe de Syntetos, Boylan e Croston):** diárias intermitentes (ADI de 1,49 a 1,84; CV² de 0,20 a 0,40); semanais suaves (ADI = 1).
- **Autocorrelação:** diária fraca (maior: lag 7 do item C = 0,30); Ljung–Box não rejeita ruído; semanal não testável de forma útil (n = 10).
- **Estacionariedade:** diárias estacionárias em nível (ADF rejeita raiz unitária e KPSS não rejeita); semanal não testável.
- **Sazonalidade por dia da semana:** confirmada na rede e nos itens B e C; **inconclusiva** em A e D (poder baixo). Razão sexta–domingo / segunda–quinta: 2,40 na rede (IC95% 1,94–3,14).
- **Outliers:** semanal do item C em 07-19 (40 unidades); sinais diários isolados (A em 08-14; D em 06-11 e 07-23).
- **Consequências a avaliar como hipóteses:** naive sazonal faz sentido na diária de B e C (e talvez na rede), mas **não** há evidência para A e D; Croston, SBA e TSB ignoram o dia da semana; na semanal (sem zeros), os métodos intermitentes perdem a razão de existir; com 10 semanas, ARIMA/ETS/Prophet semanais têm pouca base para validação.

### 5. Como conduzir (fluxo da skill)
O projeto está na fase `awaiting_user_direction`. O que falta segue os passos 6 a 7 da skill:
1. **Defina a direção comigo** (use a skill `mattpocock-skills:grilling` se estiver disponível; senão, entreviste inline, em rodadas, com uma recomendação sua por pergunta, sem perguntar o que dá para descobrir no repositório). Temas: quais candidatos entram em cada série; baselines; limites do espaço de hiperparâmetros; como tratar A e D (sazonalidade inconclusiva); o que fazer com os métodos intermitentes na semanal; critério para o Prophet; o treino mínimo e os folds já decididos (não reabrir sem motivo).
2. Registre a direção em `.ds-workflow/` com `ds_policy.py propose --kind analysis_direction`, espere eu aprovar e então `set-phase analysis_planning --decision D-xxx`.
3. Preencha o plano (`templates/pre-analysis-plan.md` da skill) para a tabela e o espaço de hiperparâmetros **antes** de olhar resultados de qualquer método; `freeze`, `propose --kind analysis_plan`, minha aprovação e `set-phase modeling`. Se achar que o plano é desproporcional para uma tabela de decisão, justifique e peça minha dispensa.
4. Execute apenas o planejado; teste o código novo com `record_test_run.py`; rode `audit_notebook.py` e `check_report.py` antes de apresentar; não consolide conclusões sem aprovação (`propose --kind conclusion|model_selection`).

### 6. Pontos de atenção
- Os testes do #5 são exploratórios e a amostra é muito curta; baselines podem vencer em várias séries, e isso é resultado, não falha.
- Venda é proxy de demanda; ruptura aparece como zero e não é distinguível.
- "Valor unitário" (planilha de SKUs) é suposição de trabalho; não afeta as séries.
- Pendências externas a repassar a mim, se relevantes: a planilha de SKUs é preço por unidade? Há explicação operacional para os 3 dias seguidos sem pedido (08-02 a 08-04) e para as 40 unidades do item C em 07-19?
- A spec `issues/1.md` ainda cita "32% a 43%"; o ADR 0003 já foi corrigido para 33% a 46% (visão de desenvolvimento).
