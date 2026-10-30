# Registro da Fase 1 — decisões, evidências e questionamentos

> **Para quem for escrever o relatório final.** Este documento foi escrito para que um agente (ou pessoa) **sem o contexto da conversa** consiga redigir o relatório completo do que foi feito. Ele separa **fato verificado** (com números e onde conferir), **decisão** (quem decidiu e por quê), **hipótese/interpretação** (ainda não confirmada) e **pendência**. Não apresente hipóteses como fatos. Atualize este arquivo a cada ticket novo.
>
> Idioma do projeto: português. Datas: `AAAA-MM-DD`. Todas as ações descritas ocorreram em 2026-10-30, salvo indicação.
>
> **Nota sobre nomes de arquivos:** este texto não cita os nomes dos arquivos DuckDB da base completa, da visão de desenvolvimento e do período OOT, porque o hook de proteção da skill de ciência de dados bloqueia escritas que os mencionam enquanto a fase for `eda`. Os nomes e caminhos estão em `src/case_mr_health/config.py` (campos `db_path`, `desenvolvimento_db_path`, `oot_db_path`, sob `data/processed/`) e na política de dados em `.ds-workflow/data-policy.json`.

## 1. O projeto em um parágrafo

MR. HEALTH é uma rede de restaurantes (~50 unidades). O objetivo é prever a **demanda** futura de cada **SKU** (4 produtos, `item A` a `item D`) a partir de **vendas** históricas, para apoiar reposição e redução de estoque. A previsão é sempre da **rede** (as unidades não são identificáveis). O histórico é muito curto (2021-06-01 a 2021-09-01, 93 dias). Especificação completa: `issues/1.md`. Vocabulário: `GLOSSARY.md`. Decisões de arquitetura: `docs/adr/0001` a `0005`. Tickets: `issues/2.md` a `issues/26.md` (a Fase 1 cobre #2 a #6).

Stack: Python 3.14, `uv`, pandas, DuckDB, scikit-learn, statsmodels, prophet, MLflow, FastAPI, cyclopts, pydantic-settings, loguru, pytest, ruff, towncrier.

## 2. Protocolo metodológico acordado com o usuário

Estas regras foram dadas pelo usuário no início da Fase 1 e valem para todo o trabalho:

1. Dados brutos em `data/raw/` são somente leitura. O PDF do case está em `data/`.
2. Os tickets **#2 e #3** (fontes, relacionamento, qualidade, calendário, os 12 dias sem pedido) podem usar o **histórico completo**, por serem auditoria de dados e não análise da dinâmica das séries.
3. O **período OOT** (ADR 0002: últimos 14 dias na diária, últimas 2 semanas na semanal) é **selado no #4, antes de qualquer EDA das séries**. A EDA (#5), a tabela de candidatos (#6) e o treino usam só a **visão de desenvolvimento**. Nenhuma célula ou consulta lê o OOT até o ticket #13.
4. Os números da Fase 0 (32% a 43% de zeros; vendas ~2,4x maiores de sexta a domingo) foram medidos com o OOT incluído. São **hipóteses a reconferir**, não fatos. Qualquer contradição com um ADR deve ser sinalizada, sem sobrescrever o ADR em silêncio.
5. Sazonalidade, estacionariedade e intermitência só são afirmadas com **teste formal**, premissas checadas e **referência com página**. Limitações de amostra são explícitas.
6. Conclusões são apresentadas ao usuário para aprovação **antes** de serem registradas no notebook ou no ticket.
7. Um ticket por vez (#2 → #3 → #4 → #5 → #6), cada um em sua branch `<ID>-<titulo_breve>`, com aprovação do usuário ao final.
8. Convenções de engenharia (`CLAUDE.md`): pacote em `src/case_mr_health/`, DuckDB, pydantic-settings, loguru (sem `print`), cyclopts, testes pytest com fixtures e `faker` sem depender das planilhas reais, ruff (aspas simples, linha de 79), fragmento towncrier por entrega, ticket marcado `Status: resolved` ao fim.
9. **Commits sem coautoria do Claude** (pedido do usuário; registrado no `CLAUDE.md`).

A skill `evidence-based-data-science-workflow` está ativa. Ela mantém uma política de acesso a dados em `.ds-workflow/` (`data-policy.json`, `state.json`, `decisions.jsonl`). Papéis: `full_data` = base completa (selada), `development_data`/`eda_sample` = visão de desenvolvimento, `test_data` = OOT (selado).

## 3. Linha do tempo por ticket

| Ticket | Branch | Commit | Status | Testes ao final |
| --- | --- | --- | --- | --- |
| #2 Base consolidada e relatório de qualidade | `2-base_consolidada` | `c35a431` | resolved | 17 |
| #3 Séries diária e semanal | `3-series_diaria_semanal` | `1a252a7` | resolved | 21 |
| #4 Partições e OOT selado | `4-particoes_oot` | `09a7887`, `ab3de1f` | resolved | 32 |
| #5 EDA das séries | `5-eda_series` | `1eba1d8`, `90a8ad5` e commit de fechamento | resolved (conclusões aprovadas) | 45 |
| #6 Tabela de candidatos | — | — | não iniciado | — |

As branches são empilhadas (cada uma parte da anterior); nada foi mesclado em `main` ainda.

### 3.1 Ticket #2 — base consolidada e relatório de qualidade

**Entregue**
- Comando `case-mr-health preparar-dados` (`src/case_mr_health/cli.py`).
- `config.py` (pydantic-settings, prefixo `CASE_MR_HEALTH_`), `logs.py` (loguru), `dados.py` (pipeline).
- Tabelas DuckDB na base completa: `sku`, `pedido`, `item_pedido` (pares pedido×SKU somados), `base_consolidada`, `qualidade_verificacoes`, `qualidade_itens_repetidos`. Relatório em markdown gerado em `data/processed/relatorio_qualidade.md` (não versionado).
- Notebook de auditoria `notebooks/01_eda_fontes_relacionamento.ipynb` (por fonte e de relacionamento). **Lê o histórico completo; é só de auditoria** e não deve ser reexecutado em análises de séries depois do selo do OOT.
- Dados brutos versionados em `data/raw/` sem alteração (hash SHA-256 registrado no relatório).
- Testes (Seam 1 da spec) com planilhas sintéticas via `faker` em `tests/conftest.py`, `tests/test_dados.py`, `tests/test_cli.py`.

**Regras do pipeline**
- Itens repetidos (mesmo SKU no mesmo pedido) têm as quantidades somadas e são listados no relatório.
- Valor do item = quantidade × valor do cadastro; valor total do pedido = soma dos valores dos itens (a coluna original está 100% vazia).
- **Rejeita, com mensagem e número da linha da planilha:** SKU sem cadastro, quantidade negativa, data inválida. **Rejeições adicionais decididas pelo agente (não estavam no ticket)**: pedido inexistente em PEDIDO, quantidade não inteira, `ID_PEDIDO` ou SKU duplicado. Quantidade zero é aceita.
- Falha rápida: qualquer rejeição aborta e não grava nada.
- Leitura com `read_xlsx` do DuckDB, `header=false`, `all_varchar=true`, intervalos abertos (`A:D`). Motivo: o DuckDB descarta a coluna de índice sem nome e converte tipos sem apontar a linha. A extensão `excel` do DuckDB exige rede na primeira execução (`INSTALL excel`).

**Fatos verificados (histórico completo)**
- 181 pedidos, 295 linhas de item, 4 SKUs; valores do cadastro 10, 15, 20, 25.
- Período 2021-06-01 a 2021-09-01; 81 dias com ao menos um pedido; portanto 12 dias sem pedido (93 − 81).
- `VALOR_TOTAL` 100% nulo (181/181).
- Integridade referencial completa: nenhum item sem pedido, nenhum item sem SKU, nenhum pedido sem item.
- 15 pares (pedido, SKU) repetidos (30 linhas); 4 deles têm quantidades idênticas (8 linhas). Resultado: 280 pares. Quantidade total 895 antes e depois (perda zero nos joins).
- Valor total reconstruído soma R$ 15.960 (mín 10, mediana 75, máx 385 por pedido).
- `ID_PEDIDO` único; o sufixo coincide com a data (AAAAMMDD) em 181/181. O prefixo "sequencial" **não é único** (147 valores distintos, 34 repetições consecutivas, nenhum salto).
- O índice sem nome de PEDIDO é, em 100% dos casos, a posição da 1ª linha de item do pedido em ITEM_PEDIDO (113 lacunas). Interpretação (hipótese): resquício de join desduplicado; não afeta a análise.
- Quantidade por linha: inteiros de 1 a 5, 53 a 67 linhas por valor. 67 a 83 linhas por SKU. 105 pedidos têm 1 SKU, 55 têm 2, 19 têm 3, 2 têm 4.
- Primeira venda: A e C em 2021-06-01; B e D em 2021-06-04. Última venda: A, C e D em 2021-09-01; B em 2021-08-29.
- A primeira linha de ITENS é um resquício (índice 0), não um dado.

**Hipótese resolvida pelo usuário:** os pares repetidos com quantidades idênticas poderiam ser lançamentos duplicados; o usuário informou que **não são duplicidade** (decisão 23). Segue-se a spec (somar).

### 3.2 Ticket #3 — séries diária e semanal

**Entregue:** `src/case_mr_health/series.py` (tabelas `serie_diaria` e `serie_semanal`), testes em `tests/test_series.py`, seção Q8 do notebook 01 (12 dias sem pedido). Pandera não foi usado (os testes cobrem as invariantes).

**Regras:** calendário do SKU = da primeira venda até o último dia com pedido na rede (2021-09-01); dia sem venda no calendário = zero imputado (`imputado = true`); semana de segunda a domingo, rotulada pela segunda-feira; semana só entra na série semanal com os 7 dias dentro do calendário do SKU.

**Fatos verificados**
- Calendários: A e C com 93 dias; B e D com 90 dias.
- Série semanal: **12 semanas completas, de 2021-06-07 a 2021-08-23, para os 4 SKUs** (confirma a spec).
- Zeros imputados no histórico completo: A 36/93 (39%), B 35/90 (39%), C 40/93 (43%), D 27/90 (30%).
- Os 12 dias sem pedido: 06-02, 06-03, 06-08, 06-16, 06-17, 06-21, 06-24, 08-02, 08-03, 08-04, 08-09, 08-11. Dia da semana: segunda 3, terça 2, quarta 4, quinta 3, **sexta a domingo 0**. Blocos de dias consecutivos: [2,1,2,1,1,3,1,1] (8 blocos; maior com 3 dias, 08-02 a 08-04). 7 dias em junho, 5 em agosto, **nenhum em julho**. Dentro do calendário de cada SKU caem 12 (A, C) e 10 (B, D) desses dias (06-02 e 06-03 são anteriores à primeira venda de B e D).
- Testes de aleatorização (exploratórios; 12 eventos): P(nenhum dos 12 dias de sexta a domingo | posição aleatória entre 93 dias) = 0,0008 (exato, hipergeométrico). P(maior bloco ≥ 3) = 0,135 (aleatório entre os 93 dias) e 0,202 (aleatório entre segunda e quinta). P(nenhum em julho | entre segunda e quinta) = 0,0054 (achado post hoc). Semente 20211030, 100.000 simulações.

**Conclusão aprovada pelo usuário:** a imputação de zero nos 12 dias é plausível (caem em dias de menor presença de pedidos; não formam um bloco longo). Os dados não separam zero verdadeiro de dado perdido ou ruptura; os 3 dias seguidos de agosto são os mais suspeitos e não são verificáveis.

### 3.3 Ticket #4 — partições e OOT selado

**Entregue:** `src/case_mr_health/particoes.py` (`particionar`, `separar_series`, `abrir_desenvolvimento`, `carregar_particoes`), campos de configuração em `config.py`, testes em `tests/test_particoes.py`. O `preparar-dados` agora também grava dois arquivos DuckDB separados: a **visão de desenvolvimento** (séries sem o OOT + tabelas `particao` e `fold` com as datas) e o **OOT** (apenas o OOT). A EDA e o treino abrem somente a visão de desenvolvimento. O particionamento usa apenas as datas dos períodos, nunca os valores de venda.

**Configuração (todas ajustáveis):** OOT diária 14 dias; OOT semanal 2 semanas; fold diária 7 dias; fold semanal 1 semana; **treino mínimo diária 42 dias**; treino mínimo semanal 6 semanas.

| Série | Desenvolvimento | OOT | Folds |
| --- | --- | --- | --- |
| Diária A, C | 2021-06-01 a 2021-08-18 (79 dias) | 2021-08-19 a 2021-09-01 | 5 |
| Diária B, D | 2021-06-04 a 2021-08-18 (76 dias) | 2021-08-19 a 2021-09-01 | 4 |
| Semanal (4 SKUs) | 2021-06-07 a 2021-08-15 (10 semanas) | 2021-08-16 a 2021-08-29 (2 semanas) | 4 |

Folds da diária A, C (treino sempre começa em 06-01; janela expansiva): teste 07-13 a 07-19, 07-20 a 07-26, 07-27 a 08-02, 08-03 a 08-09, 08-10 a 08-16. Diária B, D (treino começa em 06-04): testes 07-16 a 07-22, 07-23 a 07-29, 07-30 a 08-05, 08-06 a 08-12. Semanal: testes 07-19 a 07-25, 07-26 a 08-01, 08-02 a 08-08, 08-09 a 08-15.

**Decisão sobre o treino mínimo da diária (42 dias):** aprovada pelo usuário. Opções avaliadas: 28 dias (7 e 6 folds; só 4 ciclos semanais), **42 dias** (5 e 4 folds), 56 dias (3 e 2 folds). Motivos: múltiplo de 7, igual ao horizonte temporal do treino mínimo da semanal, folga para candidatos sazonais (que pedem ao menos 2 ciclos). É aritmética de calendário, **não** evidência de desempenho.

**Vazamento parcial entre granularidades — opção A aprovada.** O OOT diário (08-19 a 09-01) e o semanal (semanas de 08-16 e 08-23, até 08-29) não coincidem. A visão diária de desenvolvimento contém 08-16 a 08-18, dias que pertencem à semana OOT de 08-16. Opções: A (manter o ADR 0002 e registrar a limitação), B (antecipar o OOT diário para 08-16, 17 dias, contradiz o ADR), C (aceitar sem restrição). **Escolhida a A.** Regra: decisões sobre a série semanal (EDA, candidatos, hiperparâmetros) usam somente a visão semanal; por isso as análises de dia da semana usam apenas as semanas completas até 08-15.

**Decisões formais na política de dados** (`.ds-workflow/decisions.jsonl`): `D-001 split_authorization` (aprovada pelo usuário, `via: human_cli`, nota "42 dias, separação física, opção A") e `D-002 sample_provenance` (aprovada). A fase da skill avançou para `eda`. Observação: a D-001 só foi registrada como aprovada depois de o usuário reexecutar o comando de aprovação; a primeira tentativa não constava no log.

Teste central: alterar os dados do OOT (por granularidade) e rodar o pipeline de novo não muda a visão de desenvolvimento nem as partições.

### 3.4 Ticket #5 — EDA das séries (na visão de desenvolvimento)

**Entregue:** `src/case_mr_health/diagnosticos.py` (zeros com intervalo de Wilson, ADI/CV² e classes, bootstrap por blocos de semana, razão fim de semana, testes de sazonalidade, ACF/PACF/Ljung–Box, ADF/KPSS, sinalização de outliers), `tests/test_diagnosticos.py`, notebook `notebooks/02_eda_series.ipynb` (lê **somente** a visão de desenvolvimento via `abrir_desenvolvimento`; Observações e Interpretações preenchidas após a aprovação do usuário). Dependências `statsmodels` (0.15.0) e `prophet` (1.5.0) adicionadas após verificar que instalam e ajustam modelos no Python 3.14 (testado em séries sintéticas; ARIMA, ADF, KPSS, ACF/PACF, Holt-Winters e Prophet com sazonalidade semanal).

**Plano de análise** (proposto ao usuário; ele não o aprovou item a item e seguiu-se com ele, o que deve ser lido como suposição de trabalho): proporção de zeros (Wilson); ADI/CV²; ACF/PACF e Ljung–Box; ADF e KPSS; sazonalidade por dia da semana com Kruskal–Wallis, Friedman (semanas como blocos) e permutação, com correção de Holm nos 4 SKUs; razão sexta–domingo / segunda–quinta com bootstrap por blocos de semana (10.000 repetições); sinalização de outliers por MAD e IQR. Semente 20211030. Todos os testes são exploratórios.

**Observações (evidência — visão de desenvolvimento)**

- **Zeros (diária):** A 43,0% (34/79; IC95% 32,7%–54,0%), B 36,8% (28/76; 26,9%–48,1%), C 45,6% (36/79; 35,0%–56,5%), D 32,9% (25/76; 23,4%–44,1%). Todos imputados; nenhum zero observado. **Semanal:** 0/10 zeros em cada SKU (limite superior do IC95% 27,8%). Por dia da semana (diária), a proporção de zeros é maior de segunda a quinta e menor de sexta a domingo (ex.: B 0% aos domingos; C 91% às segundas).
- **Intermitência (limiares ADI 1,32 e CV² 0,49):** diárias todas "intermitentes" (ADI de 1,49 a 1,84; CV² de 0,20 a 0,40; B está mais perto do limiar). Semanais todas "suaves" (ADI = 1; CV² de 0,05 a 0,30).
- **Autocorrelação:** diária sem valor marcante nos lags 1 a 21 (maior: lag 7 do item C = 0,30, banda ±0,22). Ljung–Box não rejeita ruído nos lags 7 e 14 (p de 0,14 a 0,66). Semanal (n = 10): nada fora da banda ±0,62 nos lags 1 a 3.
- **Estacionariedade:** nas 4 diárias, ADF rejeita raiz unitária (p < 0,001) e KPSS não rejeita estacionariedade (p de 0,08 a 0,10; o valor sai truncado em 0,10 pela tabela do statsmodels) → "estacionária". Semanal: **não testável** (n = 10 < 30).
- **Sazonalidade por dia da semana** (10 semanas completas, 06-07 a 08-15; p com Holm nos 4 SKUs): item B: Kruskal–Wallis 0,013; Friedman 0,0056; permutação 0,014. Item C: Kruskal–Wallis 0,051; Friedman 0,043; permutação 0,025. Item A: 0,060; 0,200; 0,103. Item D: 0,128; 0,200; 0,103. Rede (soma dos 4 SKUs, **não** ajustada por Holm; é um quinto teste, não um dos 4): p entre 0,0000 e 0,0001.
- **Razão média diária sexta–domingo ÷ segunda–quinta** (bootstrap por blocos de semana, IC95%): rede 2,40 (1,94–3,14); A 2,19 (1,35–4,11); B 2,99 (2,05–5,17); C 2,57 (1,62–5,49); D 2,03 (1,27–3,28).
- **Outliers (apenas sinalizados, sem tratamento):** semanal do item C em 2021-07-19 com 40 unidades (mediana ~16,5), sinalizado por MAD e IQR; diária: A em 08-14 (9), D em 06-11 e 07-23 (10), só por IQR.

**Interpretações (hipóteses de trabalho; aprovadas pelo usuário em 2026-10-30)**
- O efeito fim de semana existe na rede e é detectável nos itens B e C. Para A e D os dados não permitem afirmar nem negar (poder baixo com 10 semanas; ausência de evidência não é evidência de ausência).
- As séries diárias parecem oscilar em torno de um nível fixo; as premissas dos testes (normalidade, homocedasticidade, ausência de zeros em excesso) são frágeis para contagens com muitos zeros e n = 76–79.
- A fraca autocorrelação no lag 7 contrasta com o efeito de dia da semana; o ruído das contagens pode estar mascarando. Hipótese não testada.
- A série semanal não tem zeros e é "suave", mas 10 pontos pouco permitem testar.

**Confronto com a Fase 0 e o ADR 0003 (sinalização, o ADR não foi alterado)**
- Razão ~2,4x: **confirmada** na rede (2,40).
- Zeros "32% a 43%" (Fase 0 e ADR 0003): na visão de desenvolvimento são **33% a 46%**; o item C (45,6%) **ultrapassa o limite de 43%** citado no ADR. No histórico completo com o calendário do SKU (glossário), são 30% a 43%; o "32%" do ADR corresponde ao item D contado sobre 93 dias (hipótese aritmética, não confirmada). Não muda a decisão do ADR (métodos intermitentes seguem justificados), mas o trecho está impreciso. **Decisão do usuário: corrigir o ADR 0003** (feito: o texto agora cita 33% a 46% na visão de desenvolvimento e 30% a 43% no histórico completo com o calendário do SKU). A spec `issues/1.md` ainda cita "32% a 43%" como fato da Fase 0 e não foi alterada.

### 3.5 Item C, semana de 07-19: avaliação preliminar do impacto (decisão: alternativa 1)

O usuário pediu (2026-10-30) pesquisar alternativas ou avaliar o impacto caso só esse registro seja o outlier. Abaixo, a avaliação preliminar do agente, feita por consulta direta à visão de desenvolvimento, **sem alterar dados**. Ela ainda não está numa célula de notebook; deve ser incluída se o usuário aprovar.

**Fatos observados**
- A semana de 07-19 do item C tem 40 unidades; as outras 9 semanas valem 4 a 19 (mediana 16,5; média 16,7 com a semana, 14,1 sem ela).
- **Não é um registro isolado anômalo.** Os sete dias da semana têm vendas comuns (5, 8, 5, 3, 9, 5 e 5): nenhum dia fora do intervalo diário habitual (máximo diário 9) e nenhum dia sem venda. Na série diária do item C não há outlier. O 40 semanal nasce de uma semana **sem nenhum dia zerado** (as demais semanas têm vários), isto é, é um efeito de agregação.
- Na rede, a semana de 07-19 soma 98 unidades (a maior; mediana 70, MAD 12), puxada também pelo item D (30). Os itens A e B ficaram abaixo da média. Para a rede, o z robusto fica em cerca de 1,6 (não é outlier pela regra usada).
- O CV² semanal do item C cai de 0,30 para 0,13 sem essa semana; a classificação continua "suave" nos dois casos.
- **Impacto no backtest semanal:** a semana 07-19 é o **teste do fold 1** (treino de 06-07 a 07-18). O erro absoluto do naive (previsão = semana anterior) é 22 nessa semana e 23 na seguinte (a previsão da semana seguinte parte do 40). O MAE do naive nas 4 semanas de teste é 14,25 com elas e 6,0 sem as duas. A escala do MASE (erro do naive no treino de 6 semanas) é 4,2, e o MASE do naive no fold 1 é 5,24. Ou seja, uma única semana domina a métrica do item C na semana; modelos que suavizam o nível (média, ETS) são menos afetados do que o naive.

**Alternativas de tratamento (para decisão do usuário)**
1. **Manter e relatar a sensibilidade:** calcular as métricas do item C com e sem a semana (e com e sem os folds 1 e 2) e mostrar a diferença. Não altera dados; custo baixo.
2. **Limitar (winsorizar) o valor semanal** a uma cerca (por exemplo, 3 IQR além do centro dos 50%). Altera a série semanal, que deixa de bater com a soma da diária (teste do ticket #3 exige igualdade), e é um tratamento que exige aprovação.
3. **Substituir por estimativa consistente com o restante** (mediana ou interpolação). Mesma ressalva do item 2.
4. **Variável de intervenção** (indicadora da semana) nos candidatos que a aceitam (ARIMA/SARIMA com regressor, Prophet), sem tocar na série; não se aplica a naive, média e ETS simples.
5. **Métricas e perdas robustas** (por exemplo, mediana dos erros) como complemento, sem alterar a série.
6. **Investigar a origem** (consultar a operação) — o usuário informou que não há explicação.

**Referência consultada:** Hyndman e Athanasopoulos, *Forecasting: Principles and Practice*, 3ª ed., seção 13.9, "Dealing with outliers and missing values": substituir outliers por valores faltantes ou por uma estimativa mais consistente é razoável se forem erros ou não se repetirem; "simplesmente substituir outliers sem pensar em por que ocorreram é uma prática perigosa" (tradução livre), pois eles podem trazer informação sobre o processo; o texto sugere STL robusto e sinalização por 3 IQR sobre o resto (https://otexts.com/fpp3/missing-outliers.html; sem número de página).

**Decisão do usuário (2026-10-30): alternativa 1.** A recomendação do agente era: alternativa 1 (manter e mostrar sensibilidade), com as alternativas 4 e 5 como complemento para os candidatos que as aceitam. Evitar 2 e 3 enquanto não houver razão para crer que o registro é erro, porque o dado diário é consistente e as alternativas 2 e 3 quebrariam a igualdade entre as séries diária e semanal.

## 4. Decisões consolidadas

| # | Decisão | Quem | Justificativa | Onde está registrado |
| --- | --- | --- | --- | --- |
| 1 | Protocolo de OOT selado antes da EDA; #2 e #3 usam histórico completo | Usuário | Preservar a independência do OOT | Seção 2 |
| 2 | Tratar números da Fase 0 como hipóteses | Usuário | Foram medidos com OOT incluído | Seção 2 |
| 3 | Rejeições adicionais no pipeline, falha rápida, quantidade zero aceita | Agente (informado, sem objeção) | Evitar perda silenciosa nos joins | `dados.py`, testes |
| 4 | Remover do notebook 01 a última venda, os dias com venda por SKU e o histograma de pedidos por dia | Agente propôs; usuário aprovou implicitamente ("pode seguir") | Estavam no limite do que foi autorizado (dinâmica incluindo OOT) | Notebook 01 |
| 5 | Conclusão sobre os 12 dias sem pedido | Usuário aprovou | Seção 3.2 | Notebook 01 (Q8) |
| 6 | "Valor unitário" é suposição de trabalho (PDF do case é silencioso sobre a planilha 3) | Usuário aprovou | Seção 5, item 3 | Notebook 01 (Q3), `GLOSSARY.md` |
| 7 | Treino mínimo diário = 42 dias | Usuário | Seção 3.3 | `issues/4.md`, D-001 |
| 8 | Separação física da visão de desenvolvimento e do OOT | Usuário | Impedir leitura acidental | D-001 |
| 9 | Opção A para o vazamento entre granularidades | Usuário | Manter o ADR 0002, limitação registrada | `issues/4.md`, D-001 |
| 10 | Procedência da amostra de EDA (visão de desenvolvimento) | Usuário | Exigência da política de dados | D-002 |
| 11 | Notebook 01 = só auditoria (histórico completo); notebook 02 = só visão de desenvolvimento | Agente | Impedir mistura de papéis de dados | Seções 3.1 e 3.4 |
| 12 | Commits sem coautoria do Claude | Usuário | Preferência do usuário | `CLAUDE.md` |
| 13 | **Manter a série diária** para testar os métodos de demanda intermitente (Croston, SBA, TSB) e os baselines | Usuário | Seção 5, itens 6 e 7 | Esta seção |
| 14 | Criar este registro e mantê-lo atualizado para o relatório final | Usuário | Relatório final por agente sem contexto | Este arquivo |
| 15 | Aprovar as conclusões da EDA do #5 (seção 3.4) | Usuário | Revisão dos resultados apresentados | Notebook 02, `issues/5.md` |
| 16 | Corrigir o ADR 0003 (faixa de zeros) | Usuário | Divergência do item C (45,6%) | `docs/adr/0003-candidatos-de-algoritmo.md` |
| 17 | Citar as referências normalmente no notebook, sem marcá-las como não verificadas | Usuário | Preferência de apresentação | Notebook 02 |
| 18 | O #6 será conduzido por outro agente, com a skill de ciência de dados, a partir de `docs/relatorio/continuacao-6.md` | Usuário | Continuidade com contexto novo | Esse arquivo |
| 19 | **Não corrigir a spec** (`issues/1.md`) quanto aos "32% a 43%"; acrescentar uma observação de que o dado de treino (visão de desenvolvimento) deu resultado diferente (33% a 46%) | Usuário | Preservar o texto da Fase 0 e documentar a divergência | `issues/1.md` (blockquote em "Dados") |
| 20 | Manter a suposição de que a planilha de SKUs é o preço por unidade | Usuário | Sem confirmação externa; afeta só valores financeiros | `GLOSSARY.md`, notebooks 01 e 02 |
| 21 | Sem explicação operacional para os 3 dias seguidos sem pedido (08-02 a 08-04) nem para as 40 unidades do item C na semana de 07-19. **Os 3 dias zerados não precisam de tratamento** (permanecem zeros imputados). **Item C:** pesquisar alternativas de tratamento ou avaliar o impacto caso só esse registro seja o outlier (ver seção 3.5); depois escolhida a alternativa 1 (decisão 24) | Usuário (versão revisada em 2026-10-30; a anterior os tratava ambos como outliers) | Ausência de explicação | Notebooks 01 e 02, seção 3.5 |
| 24 | **Item C, semana de 07-19: alternativa 1** — manter o valor (40) e relatar a sensibilidade das métricas, sem alterar a série. Calcular as métricas do item C semanal com e sem essa semana (e com e sem os folds 1 e 2). Alternativas 4 (variável de intervenção) e 5 (métricas robustas) ficam como complemento opcional para os candidatos que as aceitam; as alternativas 2 e 3 (limitar ou substituir) estão descartadas por ora | Usuário | Dado diário consistente; não alterar a série preserva a igualdade entre a diária e a semanal | Seção 3.5, `issues/7.md` (comentário) |
| 23 | Os pares de itens repetidos (inclusive os 4 com quantidades idênticas) **não são duplicidade**; as quantidades seguem somadas | Usuário | Resposta à dúvida do ticket #2 | Notebook 01, seção 3.1 |
| 22 | Não executar operações de git até nova ordem (as alterações de documentação desta rodada ficam sem commit) | Usuário | Controle do histórico pelo usuário | Este arquivo |

Decisões **ainda não tomadas**: ver seção 8.

## 5. Questionamentos do usuário e respostas dadas (Q&A)

Cada item é uma pergunta feita pelo usuário durante a Fase 1, com a resposta resumida e o status.

1. **"30% a 43% de zeros imputados não é muita coisa? Chega a quase 50% da série."** Resposta: sim, é grande. "Zero imputado" é um dia sem venda registrada, não dado inventado; só é problema se for dado perdido ou ruptura (indistinguível nos dados). Implicação: motivo dos métodos de demanda intermitente (ADR 0003); métricas diárias ficam instáveis. A classificação formal fica para a EDA (#5), já feita (seção 3.4). Status: respondida.
2. **"Qual a última data com venda do item C?"** Resposta: 2021-09-01, o último dia do histórico. Status: respondida (veio do notebook 01 antes da remoção dessa coluna).
3. **"A planilha 3 pode ser o estoque e não o valor unitário? Verifique se os valores coincidem com quantidades vendidas."** Teste (histórico completo, incluindo OOT, por ser auditoria do significado do cadastro):

   | SKU | Valor | Total vendido | Maior venda em um dia | Dias com venda igual ao valor | Semanas iguais ao valor (de 12) | Meses iguais |
   | --- | --- | --- | --- | --- | --- | --- |
   | A | 10 | 211 | 9 | 0 | 1 | 0 |
   | B | 15 | 217 | 10 | 0 | 2 | 0 |
   | C | 20 | 216 | 9 | 0 | 0 | 0 |
   | D | 25 | 251 | 10 | 0 | 0 | 0 |

   Maior quantidade por pedido: 8, 7, 9 e 6 (A a D). A venda acumulada ultrapassa o valor em 06-09 (A), 06-06 (B), 06-18 (C) e 06-14 (D) sem reposição visível. Conclusão: a hipótese "o valor é uma quantidade vendida" não se sustenta; "é estoque" **não é refutável** com estes dados (estoque pontual não precisa coincidir com vendas). Indícios para preço: progressão regular 10-15-20-25 e a existência da coluna `VALOR_TOTAL` em PEDIDO (indireto). **O PDF do case não diz o que é a planilha 3** (informado pelo usuário; o agente não conseguiu ler o PDF no ambiente por falta de leitor de PDF). Decisão: manter "valor unitário" como suposição de trabalho; afeta só valores financeiros, não as quantidades, as séries nem as recomendações. Em 2026-10-30 o usuário decidiu manter a suposição de que é o preço por unidade (decisão 20). Status: respondida e decidida.
4. **"Explique as conclusões sem abreviações e diga se o modelo semanal parece viável."** Resposta (julgamento do agente, não resultado de teste): viável como baseline sólido, fraco para afirmar precisão. A favor: toda semana tem venda; o efeito de dia da semana some ao somar a semana; métodos simples funcionam bem. Contra: apenas 10 semanas completas (4 testes por produto com treino mínimo de 6 semanas); estabilidade e autocorrelação não testáveis; palpite (não testado) de que métodos simples terão desempenho parecido com os complexos; a regra do ADR 0004 (4 vs 2 semanas, cerca de 7 variações históricas) tem base estatística muito frágil. Um resultado "Insuficiente" em vários produtos seria honesto. Status: respondida; a confirmação depende do backtest (#7 em diante).
5. **"Dá para eliminar o OOT para ter mais dados de treino e teste? Isso daria mais testes ao modelo semanal?"** Resposta: tecnicamente sim, mas não recomendado. Ganho: semanal 10→12 semanas (4→6 testes), diária 76–79→90–93 dias (A, C: 5→7 testes; B, D: 4→6). Custo: perde a única avaliação independente (risco de erro otimista com vários candidatos em 4–6 pontos) e a validação do horizonte de 2 semanas (os folds têm 1 semana). Mitigações: retreinar o modelo escolhido com todos os dados depois da avaliação (**não definido no ADR 0002; sugerido para a Fase 4**); reduzir o treino mínimo semanal de 6 para 5 semanas (5 testes); comparar métodos somando o erro dos 4 produtos (24 pontos, não independentes). Qualquer mudança contradiz o ADR 0002 e a D-001 e exigiria nova decisão (`resplit`). Recomendação do agente: manter o OOT. **O usuário não pediu mudança; o protocolo atual segue vigente.** Status: respondida; sem alteração.
6. **"Muitos zeros tornam o modelo diário fraco ou instável?"** Resposta: mais difícil de avaliar e de prever, não inutilizável. Dificuldades: métricas percentuais não funcionam com zero; o erro fica dominado pelos dias com venda; ARIMA/ETS supõem valores contínuos e simétricos; intervalos limitados em zero; métodos intermitentes ignoram o dia da semana. Atenuante: os zeros não são aleatórios (dependem do dia da semana). Hipótese do agente: confiança baixa ou "Insuficiente" em vários produtos na diária. Status: respondida.
7. **"Qual o impacto de descartar a modelagem diária?"** Resposta: perderia as histórias 1, 3 e 5 da spec (previsão de 14 dias, alternar granularidade, histórico com previsão), a visão por dia da semana (efeito forte) e a razão de ser dos métodos intermitentes; ganharia 4 modelos em vez de 8, ausência do vazamento entre granularidades e menos métricas frágeis; as recomendações (ADR 0004) já usam só o modelo semanal. Exigiria rever ADRs 0001, 0002 e 0003, a spec, vários tickets de #6 a #26 e as decisões 7–9. Alternativa intermediária descrita: manter a diária só com baselines e métodos intermitentes. **Decisão do usuário: manter a série diária para testar esses modelos** (decisão 13). Status: decidida.
8. **"O que são métodos de demanda intermitente?"** Resposta: Croston (1972) estima separadamente o tamanho da venda e o intervalo entre vendas, previsão = tamanho ÷ intervalo (tende a superestimar); SBA (Syntetos–Boylan) é o Croston com correção do viés; TSB (Teunter–Syntetos–Babai) estima a probabilidade de venda em cada período e a atualiza também nos dias sem venda. Limitação: previsão constante, sem dia da semana; pensados para séries longas. Serão implementados em código próprio (ADR 0003). Status: respondida.

## 6. Limitações (devem constar do relatório final)

- Histórico de 93 dias (2021-06-01 a 2021-09-01), 4 SKUs, 181 pedidos. 76–79 dias e 10 semanas na visão de desenvolvimento.
- Sem identificação de unidade, sem dados de estoque, pedidos de compra ou prazos de reposição. Venda é proxy de demanda; ruptura aparece como zero.
- O significado da planilha de SKUs (valor unitário) é inferido e não confirmado.
- Os testes estatísticos são exploratórios, com n pequeno, premissas aproximadas e séries de contagem com muitos zeros; p-valores não são prova.
- O vazamento parcial entre granularidades (08-16 a 08-18) foi aceito na opção A.
- Dados com aparência sintética (quantidades de 1 a 5, preços redondos): padrões aparentes exigem teste formal (ver spec, "Further Notes").
- Os números da Fase 0 e do ADR 0003 sobre zeros divergem da visão de desenvolvimento (seção 3.4).

## 7. Referências

**Consultadas e verificadas no acervo local** (Kutner, Nachtsheim, Neter e Li, *Applied Linear Statistical Models*, 5ª ed., 2005; chave `kutner2005`):
- Teste de aleatorização/permutação: p. 714 (impresso), que também adverte que esses testes são conservadores em amostras pequenas.
- Kruskal–Wallis, aproximação χ² com grupos de cinco ou mais: pdf p. 830 (impresso p. 796, página inferida).
- Friedman, equivalência com o teste F de ranks em blocos casualizados: pdf p. 934–935 (impresso p. 900–901).
- Bootstrap (no contexto de regressão): pdf p. 494 (impresso p. 460). **Não** há apoio direto no acervo para o bootstrap por blocos de semana aplicado a uma razão.
- Autocorrelação em séries temporais: capítulo 12 (impresso p. 503–506), mas pelo Durbin–Watson, não pelo Ljung–Box.

**Consultadas externamente (sem número de página):**
- Syntetos, A. A.; Boylan, J. E.; Croston, J. D. (2005). *On the categorization of demand patterns*. Journal of the Operational Research Society, 56(5), 495–503. Dados bibliográficos confirmados no registro da Lancaster (https://eprints.lancs.ac.uk/id/eprint/73095); limiares ADI 1,32 e CV² 0,49 confirmados por fontes secundárias (artigo de 2020 na *Sādhanā*, https://core.ac.uk/download/289273745.pdf), **não pelo artigo original**. Há divergência entre fontes sobre desigualdades estritas ou não na fronteira dos limiares.
- Hyndman, R. J.; Athanasopoulos, G. *Forecasting: Principles and Practice* (3ª ed.), seção 9.1, "Stationarity and differencing": H0 do KPSS é a estacionariedade; p-valor reportado entre 0,01 e 0,1 (https://otexts.com/fpp3/stationarity.html).

**Citadas no notebook como referência de método, sem consulta do texto pelo agente (não atribuir números de página a elas no relatório):** Dickey e Fuller (1979) para o ADF; Ljung e Box (1978); Holm (1979); regra de Iglewicz e Hoaglin para o z robusto de MAD; Croston (1972); Teunter, Syntetos e Babai (TSB). O acervo local **não** contém Syntetos e Boylan, ADF/KPSS, Ljung–Box nem Holm.

## 8. Pendências e perguntas em aberto

1. ~~Aprovação das conclusões da EDA (#5)~~ — **feita**; ~~correção do ADR 0003~~ — **feita**; referências: citadas sem página, conforme decisão 17.
2. Plano de análise do #5 seguido sem aprovação explícita item a item (seção 3.4); as conclusões resultantes foram aprovadas.
3. Retreino do modelo escolhido com todos os dados após a avaliação final: não está no ADR 0002 (sugestão para a Fase 4, #13/#14).
4. **Perguntas respondidas pelo usuário em 2026-10-30:** a planilha de SKUs segue como preço por unidade (suposição mantida); os pares repetidos não são duplicidade; não há explicação para os três dias sem pedido (sem tratamento) nem para as 40 unidades do item C (decisões 20, 21 e 23). O tratamento do item C na semana de 07-19 foi decidido (alternativa 1, decisão 24): a análise de sensibilidade será feita no backtest (#7 em diante).
5. **Ticket #6 (tabela de candidatos por série) não iniciado.** Instruções para o agente que o conduzirá: `docs/relatorio/continuacao-6.md`. Ao fechar o #6 o usuário pediu uma **apresentação de encerramento da Fase 1** com: o que foi feito, testes, decisões, limitações e conclusões. Também sugerir versão (Semantic Versioning) para o `towncrier build` ao concluir um marco (`CLAUDE.md`).
6. ~~Spec com "32% a 43%"~~ — resolvido pela decisão 19: texto mantido, observação acrescentada.
7. Os tickets seguintes (#7 a #26) estão em `issues/`. Com a decisão de manter a diária, os candidatos diários (Croston, SBA, TSB e baselines) seguem no ticket #10 (`issues/10.md`).

## 9. Reprodução e verificação

```bash
uv sync
uv run case-mr-health preparar-dados        # base, séries, relatório de qualidade, visão de desenvolvimento e OOT
uv run poe format && uv run poe test         # lint + 45 testes + cobertura
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_eda_series.ipynb
python3 ~/.claude/skills/evidence-based-data-science-workflow/scripts/ds_policy.py status
```

- Evidência dos testes (skill): `.ds-workflow/test-evidence/test-run-20261030T024244-226914.json` e `.ds-workflow/test-evidence/test-run-20261030T031940-253638.json` (45 testes passaram) e, antes da criação da política, o registro `test-evidence/` na raiz (ignorado pelo git).
- O notebook 01 só deve ser reexecutado como auditoria (lê o histórico completo). Depois do selo, o hook da skill bloqueia comandos e escritas que citam o histórico completo ou o OOT enquanto a fase for `eda`.
- Auditoria do notebook 02 com `audit_notebook.py`: 0 erros; dois avisos de "linguagem causal" numa célula de método (falso positivo, o texto descreve o teste e não afirma causa).
- Testes por módulo: dados e CLI (Seam 1), séries, partições, diagnósticos.

## 10. Roteiro sugerido para o relatório final

1. Contexto e objetivo (seção 1). 2. Dados: fontes, qualidade, regras de consolidação (3.1). 3. Séries e calendário, 12 dias sem pedido (3.2). 4. Protocolo de partições e OOT, decisões e limitações (3.3 e seção 4). 5. EDA das séries: zeros, intermitência, autocorrelação, estacionariedade, sazonalidade, outliers (3.4). 6. Confronto com a Fase 0 e os ADRs. 7. Questionamentos e decisões (seções 4 e 5). 8. Limitações (6). 9. Referências e o que não foi verificado (7). 10. Próximos passos (8) e proposta de versão. Use sempre "venda" para o observado e "demanda" para o previsto; não afirme ruptura sem dados de estoque (glossário).
