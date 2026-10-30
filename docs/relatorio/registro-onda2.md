# Registro da onda 2 (#12, #14, #17)

> Regra do `CLAUDE.md` acrescentada pelo usuário em 2026-10-30. Plano: `plano-paralelizacao.md`.

| Ticket | Branch | Execução | Status | Registro |
| --- | --- | --- | --- | --- |
| #12 Seleção por série | `12-treino_selecao` | Coordenador | Código pronto, sem commit; treino aguarda a D-018 | `fase2/12.md`, `fase2/12-pre-registro.md` |
| #14 API de predição | `14-api_predicao` | Agente em worktree | Em andamento | `fase5/14.md` (no worktree) |
| #17 Changelog na API | `17-changelog_api` | Agente em worktree | Implementado, sem commit; 16 testes passam | `fase5/17.md` (no worktree) |

## Decisões do coordenador para o #14 e o #17

Layout congelado do pacote `api/`; valor unitário em configuração, pois a tabela `sku` só existe no banco completo selado; origem da previsão fixa em `desenvolvimento_fim`; resposta por período, sem agregar intervalos; confiança opcional e lida num único ponto, porque pode sair da solução; `champion` só depois do #13, com versão fixada por configuração até lá.

## Desvios do plano

- #14 e #17 correram em paralelo, embora a issue #17 declare bloqueio pelo #14: o layout congelado evita o conflito, e a inclusão do router é feita na integração.
- O #18 não entrou: é conversa com o usuário e continua pendente, bloqueando o #19.
- Os agentes rodam só os próprios testes. O critério "`poe test` verde" de cada issue fica para a integração, com a tarefa `test-rapido`.
