# Registro da onda 2 (#12, #14, #17)

> Regra do `CLAUDE.md` acrescentada pelo usuário em 2026-10-30. Plano: `plano-paralelizacao.md`.

| Ticket | Branch | Execução | Status | Registro |
| --- | --- | --- | --- | --- |
| #12 Seleção por série | `12-treino_selecao` | Coordenador | Implementado; treino real concluído uma vez | `fase2/12.md`, `fase2/12-pre-registro.md` |
| #14 API de predição | `14-api_predicao` | Agente em worktree | Implementado; 75 testes específicos passam | `fase5/14.md` |
| #17 Changelog na API | `17-changelog_api` | Agente em worktree | Implementado; 16 testes específicos passam | `fase5/17.md` |
| #27 Remoção da confiança | `27-remover_confianca` | Coordenador | Implementado e validado (2026-10-30) | `issues/27.md` |

## Decisões do coordenador para o #14 e o #17

Layout congelado do pacote `api/`; valor unitário em configuração, pois a tabela `sku` só existe no banco completo selado; origem da previsão fixa em `desenvolvimento_fim`; resposta por período, sem agregar intervalos; confiança removida pela decisão D-020/#27; `champion` só depois do #13, com versão fixada por configuração até lá.

## Desvios do plano

- #14 e #17 correram em paralelo, embora a issue #17 declare bloqueio pelo #14: o layout congelado evita o conflito, e a inclusão do router é feita na integração.
- O #18 não entrou: é conversa com o usuário e continua pendente, bloqueando o #19.
- Os agentes rodam só os próprios testes. O critério "`poe test` verde" de cada issue fica para a integração, com a tarefa `test-rapido`.

## Decisões do usuário em 2026-10-30

1. Tirar o naive das séries diárias (desvio pós-hoc, antes do OOT): D-019.
2. Remover a confiança da solução final: D-020 e #27.
3. Aceitar as decisões dos agentes do #14 e do #17 e integrar.

## Pendências da onda 2 fechadas em 2026-10-30

- **Validação do #27 e critério `poe test` dos #14 e #17:** `uv run poe lint` limpo e `uv run poe test-rapido` com 441 passados e 48 desselecionados (`lento`), em 45,5 s, na árvore com as mudanças da onda 3 ainda não commitadas. A suíte lenta não foi rodada, conforme a decisão de não repetir o treino real.
- **Inclusão do router do changelog:** já feita; `ROTEADORES` em `api/app.py` contém `predicao`, `changelog` e `consultas`.
- **Hash com artefatos reais (#14):** **não conferido**. `carregar_modelos` com o MLflow local (`data/mlflow/mlflow.db`) encontrou os 8 registros sem alias `champion` e carregou 0 modelos. A conferência depende do #13, que promove o champion.
- **#18** (especificação da regra de recomendação) segue pendente: exige conversa com o usuário e bloqueia o #19.
