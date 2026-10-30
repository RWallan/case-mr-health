# Registro da onda 2 (#12, #14, #17)

> Regra do `CLAUDE.md` acrescentada pelo usuário em 2026-10-30. Plano: `plano-paralelizacao.md`.

| Ticket | Branch | Execução | Status | Registro |
| --- | --- | --- | --- | --- |
| #12 Seleção por série | `12-treino_selecao` | Coordenador | Treino e seleção feitos; D-019 e D-020 aguardam `approve` | `fase2/12.md`, `fase2/12-pre-registro.md` |
| #14 API de predição | `14-api_predicao` | Agente em worktree | Implementado; 75 testes passam | `fase5/14.md` |
| #17 Changelog na API | `17-changelog_api` | Agente em worktree | Implementado; 16 testes passam | `fase5/17.md` |

## Decisões do coordenador para o #14 e o #17

Layout congelado do pacote `api/`; valor unitário em configuração, pois a tabela `sku` só existe no banco completo selado; origem da previsão fixa em `desenvolvimento_fim`; resposta por período, sem agregar intervalos; confiança opcional e lida num único ponto, porque pode sair da solução; `champion` só depois do #13, com versão fixada por configuração até lá.

## Desvios do plano

- #14 e #17 correram em paralelo, embora a issue #17 declare bloqueio pelo #14: o layout congelado evita o conflito, e a inclusão do router é feita na integração.
- O #18 não entrou: é conversa com o usuário e continua pendente, bloqueando o #19.
- Os agentes rodam só os próprios testes. O critério "`poe test` verde" de cada issue fica para a integração, com a tarefa `test-rapido`.

## Decisões do usuário em 2026-10-30

1. Tirar o naive das séries diárias (desvio pós-hoc, antes do OOT): D-019.
2. Remover a confiança da solução final: D-020 e #27.
3. Aceitar as decisões dos agentes do #14 e do #17 e integrar.
