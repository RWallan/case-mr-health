# Reavaliação de demonstração no OOT para quem retreina o projeto

Status: **APROVADO** pelo usuário em 2026-10-30, ponto a ponto (issue #34). Relativiza o ADR 0002 no ponto "o OOT só é usado na validação final": a avaliação cega continua sendo a única feita no #13; a repetição é de outra natureza e vem rotulada.

## Decisão

Um humano, só com o CLI, pode refazer o fluxo inteiro (preparar, treinar, selecionar, avaliar e promover) sem a skill de ciência de dados e sem forjar decisões. Para isso existe o **modo demonstração**:

- **Reavaliação não cega.** O OOT já foi aberto (#13, D-021) e as 8 séries foram publicadas com base nele. Abri-lo de novo é uma **reavaliação de demonstração**: não estima desempenho de forma independente. Todo relatório, run e versão dela carrega esse aviso. As métricas da avaliação original (#13, `docs/relatorio/fase4/13-avaliacao-final.md`) continuam sendo a única evidência cega.
- **Caminho separado (`--demonstracao`).** `avaliar-final --demonstracao` não consulta os portões do `.ds-workflow/` (fase, protocolo congelado, decisões aprovadas) e **nunca altera** `state.json`, `decisions.jsonl` nem `final-evaluation-attempt.json`. Grava o seu próprio marcador e relatório em `.ds-workflow/demonstracao/` e `docs/relatorio/demonstracao/`, com data. Pode ser repetido; cada execução gera um relatório novo. O modo sem a flag continua como era: abre o OOT uma única vez.
- **Promoção com justificativa.** `promover --demonstracao --justificativa "<texto>"` atribui o `champion` sem `D-xxx`. O texto, o horário e o usuário do sistema ficam em tags da versão no MLflow. Só é aceita uma versão que passou pela reavaliação de demonstração (tag gravada por ela); isso impede um `champion` que nunca tocou o OOT. O `retreinar` (#35) chama a promoção das 8 séries com a justificativa padrão "retreino total em modo demonstração", substituível por `--justificativa`.
- **Rótulo no registro.** As versões e runs da reavaliação levam a tag `modo=demonstracao`. A API e o dashboard não precisam mudar: a origem continua visível pelo `run_id`.

## Alternativas descartadas

- **Ciclo novo (`--ciclo`)**, arquivando o marcador e reabrindo a tentativa única: continuaria exigindo as decisões aprovadas por `ds_policy.py`, que não está no repositório.
- **Promoção automática do `selecionado` com confirmação interativa**: deixa menos rastro do motivo e depende do critério do #12.
- **Parar antes do OOT** (retreinar e promover só com o backtest): evitaria a leitura não cega, mas o `champion` não seria avaliado fora da amostra.

## Consequências

- O ADR 0002 passa a ter uma exceção explícita; o OOT original segue sendo o único com valor de teste cego, e `GLOSSARY.md` define a reavaliação de demonstração.
- O retreino total em outra máquina gera versões novas no registro versionado (#32) sem apagar as atuais; voltar ao estado original é `git checkout -- data/mlflow`.
- O relatório da reavaliação deve ser lido como diagnóstico de reprodutibilidade, não como prova de generalização.
- A implementação está na issue #37.
