# Registro da Onda 4 — explicação, e-mail mockado e telas do dashboard

Data: 2026-10-30  
Escopo: issues #20, #21, #23, #24 e #25, conforme
`docs/relatorio/plano-paralelizacao.md`. Registros por ticket em
`docs/relatorio/fase5/<ID>.md`.

## Tickets

| Ticket | Branch | Commit | Entrega |
| --- | --- | --- | --- |
| #20 | `20-explicacao_llm` | 6d3de9f | `explicacao: {texto, origem}` em `GET /recomendacoes/{sku}`; LLM com fallback em template |
| #21 | `21-email_mockado` | 4132db9 | `POST /alertas/email`, envio sempre simulado |
| #24 | `24-dashboard_entrada` | dc1664e | Entrada manual e XLSX no dashboard |
| #25 | `25-sumario_comparacao` | a7ca564 | Aba `Escopo` e `X-Escopo` no XLSX, comparação entre SKUs, links de Swagger e changelog |
| #23 | `23-recomendacoes_dashboard` | e947798 | Lista de recomendações e e-mail mockado no dashboard |

A branch `23-recomendacoes_dashboard` é a base de integração: contém as
outras quatro (um conflito em `frontend/src/App.svelte`, aditivo, resolvido
mantendo os dois lados).

## Fatos verificados

- Na base de integração: `uv run poe lint` limpo; `uv run poe test-rapido`
  626 passaram, 48 lentos excluídos (174 s); `npm run build` sem erros.
- Nenhum treino e nenhuma suíte lenta rodaram.

## Limitações

- O LLM real nunca foi chamado; o dashboard não foi aberto em navegador.
- Cada carga da lista de recomendações faz 4 chamadas; com chave de LLM,
  são 4 chamadas pagas, sem cache.
- Os PRs ainda não foram abertos.

## Integração (2026-10-30)

Um PR por ticket, mesclado pelo GitHub na ordem #20 (PR #20), #21 (PR #21), #24 (PR #22), #25 (PR #23) e #23. O GitHub recusou a aprovação do próprio autor ("Can not approve your own pull request"); o merge foi feito a pedido explícito do usuário, sem aprovação registrada. Decisões do usuário no mesmo dia: o LLM é agnóstico ao provedor (litellm), com modelo e chave informados pelo usuário no dashboard (cabeçalhos `X-LLM-Modelo` e `X-LLM-Chave`); os alertas continuam só semanais.
