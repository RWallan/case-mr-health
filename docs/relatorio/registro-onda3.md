# Registro da Onda 3 — entregas parciais e portões

Data: 2026-10-30  
Branch de integração: `main` (pedido explícito do usuário).  
Escopo: issues #13, #15, #16, #19 e #22, conforme
`docs/relatorio/plano-paralelizacao.md`.

## Protocolo vigente

- A skill `evidence-based-data-science-workflow` foi lida em
  `/home/rwallan/.claude/skills/evidence-based-data-science-workflow/SKILL.md`.
- `.ds-workflow/state.json` permanece na fase `modeling`.
- O OOT está selado. D-019 (seleção final) e D-020 (remoção da confiança)
  constam como propostas sem eventos `approved` no ledger.
- O protocolo `docs/analysis/protocolo-avaliacao-final.md` foi congelado
  (SHA-256 `88defe79d130afdcd81c43a386163a9fbd86922957a97f19175432c32c11e360`)
  e a decisão D-021 foi proposta; ainda requer aprovação humana.
- Nenhum comando de avaliação final abriu o banco OOT e nenhuma aprovação foi
  registrada pelo agente.
- A confiança foi removida dos escopos das issues #13, #16 e #22, conforme a
  decisão conversacional do usuário; a formalização D-020 segue pendente no
  fluxo de política.

## Tickets

| Ticket | Status nesta entrega | Registro |
| --- | --- | --- |
| #13 | Preparado, execução pendente | Protocolo congelado e D-021 proposta; D-019, D-020 e D-021 precisam ser aprovadas pelo usuário e a fase precisa avançar para `final_evaluation`. Sem execução do OOT. |
| #15 | Escopo fechado, não implementado | Decisão do usuário (2026-10-30): sem campo `quantidade`; contrato do #14 inalterado; critério de zero × ausente descartado. Resta batch e XLSX com template, sem o campo. |
| #16 | Implementado | `GET /previsoes`, `GET /previsoes/exportacao.xlsx`, `GET /modelos`; histórico paginado, XLSX sem truncamento e metadados do Registry. |
| #19 | Implementado | #18 foi aprovada (commit e66357d). `GET /recomendacoes/{sku}`, regra pura em `recomendacao.py`, 5 casos do #18 e bordas testados. Detalhes em `docs/relatorio/fase5/19.md`. |
| #22 | Implementado | Dashboard Svelte/Vite e rota `GET /series/{sku}/{granularidade}` usando só o banco de desenvolvimento. |

## Fatos verificados

- `tests/test_api_consultas.py tests/test_api_predicao.py`: 85 testes passaram
  em 10,85 s; evidência em
  `.ds-workflow/test-evidence/test-run-20261030T080514-907249.json`.
- Suíte rápida completa: 441 passaram, 48 testes lentos foram excluídos;
  evidência em `.ds-workflow/test-evidence/test-run-20261030T080638-911245.json`.
- `npm run build` em `frontend/`: Vite concluiu sem erros em 0,735 s.
- Ruff nos módulos Python novos/alterados passou após a última correção de
  estilo. A suíte completa do projeto não foi executada.
- `git worktree list` mostrou somente o checkout principal em `main`; a lista
  local de branches mostrou somente `main`.

## Decisões e limitações

- A exportação tem a coluna `Recomendação`, preenchida só nas linhas geradas
  por `GET /recomendacoes/{sku}` (decisão do usuário em 2026-10-30; o resultado
  é gravado no histórico, não recalculado). Previsões de `POST /predicoes`
  ficam com a célula vazia.
- A interface é um primeiro caminho funcional, sem roteador, biblioteca de
  estado ou testes de navegador, em linha com o escopo simplificado aprovado
  para #22.
- A API da predição usa a origem fixa do treino (limite validado de 14 dias ou
  2 semanas após o treino). A interface apresenta esse limite; não há retreino
  nem previsão para a data atual enquanto o modelo publicado não cobrir essa
  data.
- Nenhuma conclusão sobre desempenho OOT foi produzida.

## Reprodução

```bash
python3 /home/rwallan/.claude/skills/evidence-based-data-science-workflow/scripts/record_test_run.py -- uv run pytest tests/test_api_consultas.py tests/test_api_predicao.py -q
uv run ruff check src/case_mr_health/api/app.py src/case_mr_health/api/historico.py src/case_mr_health/api/rotas/consultas.py src/case_mr_health/api/schemas/consultas.py src/case_mr_health/api/servicos/consultas.py tests/test_api_consultas.py tests/test_api_predicao.py
cd frontend && npm run build
```

## Pendências para concluir a onda

1. (Resolvida em 2026-10-30) Sem campo `quantidade` no #15. Pendente: implementar batch e XLSX; avaliar o mock de bucket de retreino no frontend (sem ticket).
2. (Resolvida em 2026-10-30) 503 para SKU válido sem modelo semanal foi confirmado.
3. Usuário aprovar formalmente D-019, D-020 e D-021 e avançar a fase para
   `final_evaluation`; só então executar #13 uma vez.
4. Registrar a decisão de publicação por série antes de atribuir `champion`.
