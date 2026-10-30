# EDA review checklist

Notebook: `notebooks/02_eda_series.ipynb` (EDA das séries, ticket #5). Evidência de testes: `.ds-workflow/test-evidence/test-run-20261030T031940-253638.json` (45 passaram).

## Data access
- [x] Only the authorised EDA data (training split by default) was read for exploration (no full dataset, no test split). O notebook 02 lê somente a visão de desenvolvimento via `abrir_desenvolvimento`. Os tickets #2 e #3 usaram o histórico completo por autorização explícita do usuário (auditoria de dados, antes da política de dados existir); o OOT nunca foi lido.
- [x] Split and EDA data documented: split method, sizes, seed, columns used; origin, unit, limitations, restrictions (`issues/4.md`, `docs/relatorio/registro-fase1.md`, D-001 e D-002)
- [x] Schema/metadata inspection of other files used only `inspect_schema.py` or documentation. N/A: nenhuma inspeção de outros arquivos; as datas das partições vêm da função `particionar`.

## Questions and coverage
- [x] Every analysis answers a stated question; unanswered questions are listed (Q1 a Q9 no notebook; perguntas abertas ao usuário listadas)
- [x] Structure, granularity and unit of observation described (seção 0 do notebook; notebook 01)
- [x] Variable meanings and units verified (dictionary/user), unknown-value codes found. N/A parcial: o significado da planilha de SKUs (valor unitário) é suposição de trabalho documentada, pois o PDF do case não o define.
- [x] Distributions and summary measures (with counts)
- [x] Missing data amount and patterns. N/A para as séries: zeros são imputados e analisados em Q1; nulos das fontes estão no notebook 01 (VALOR_TOTAL 100% vazio).
- [x] Duplicates, inconsistencies, invalid values (notebook 01: 15 pares repetidos somados e listados)
- [x] Extreme values / potentially influential observations flagged (not removed) (Q7)
- [x] Relations between variables. N/A: o alvo é a venda por SKU; a relação com o dia da semana está em Q5 e Q6. Não há outras variáveis explicativas.
- [x] Group differences (with group sizes) (Q5 e Q6, por dia da semana, 10 semanas)
- [x] Temporal behaviour and dependence (Q3, Q4, Q5)
- [x] Class balance of candidate targets. N/A: o alvo é uma contagem, não uma classe.
- [x] Representativeness of the sample and possible bias sources. Limitações declaradas: 76–79 dias e 10 semanas; venda como proxy de demanda; rupturas e dados perdidos indistinguíveis de zeros; dados de aparência sintética.
- [x] Limitations affecting later analyses (seção Limitações do notebook; seção 6 do registro)

## Correctness
- [x] Calculations, filters and transformations re-checked (funções de `diagnosticos.py` testadas contra valores calculados à mão e dados sintéticos de padrão conhecido; zeros e semanas conferidos com o pipeline do ticket #3)
- [x] Figures: appropriate type, labelled axes with units, legends, readable scales
- [x] Code matches outputs; notebook executed top to bottom in a fresh kernel (`jupyter nbconvert --execute`)
- [x] Helper code has tests, run via record_test_run.py (evidence file cited acima)
- [x] audit_notebook.py passes (no errors). 0 erros; 2 avisos de "linguagem causal" sobre células de método e resumo (falsos positivos: o texto descreve testes e associações).

## Claims
- [x] Observations separated from interpretations; alternatives listed
- [x] No conclusions, causal claims, target/variable/model decisions presented as settled (PROPOSED where needed). As interpretações foram aprovadas pelo usuário como hipóteses de trabalho; nenhuma decisão de modelo foi tomada.
- [x] Exploratory tests (if any) labelled exploratory, multiplicity acknowledged (Holm nos 4 SKUs; a linha da rede está fora da correção e isso é dito)
- [x] Every statement is supported by a cell/figure/table in the notebook
