# Registro da Onda 3 — entregas parciais e portões

Data: 2026-10-30  
Branch de integração: `main` (pedido explícito do usuário).  
Escopo: issues #13, #15, #16, #19 e #22, conforme
`docs/relatorio/plano-paralelizacao.md`.

## Protocolo vigente

- A skill `evidence-based-data-science-workflow` foi lida em
  `/home/rwallan/.claude/skills/evidence-based-data-science-workflow/SKILL.md`.
- `.ds-workflow/state.json` permanece na fase `modeling`.
- **Atualização 2026-10-30:** D-019, D-020 e D-021 foram aprovadas e o OOT foi aberto uma única vez pelo #13. Texto anterior: o OOT estava selado e as decisões constavam como propostas.
- O protocolo `docs/analysis/protocolo-avaliacao-final.md` foi congelado
  (SHA-256 `88defe79d130afdcd81c43a386163a9fbd86922957a97f19175432c32c11e360`)
  e a decisão D-021 foi proposta; ainda requer aprovação humana.
- (Superado em 2026-10-30, ver abaixo.) Nenhum comando de avaliação final abriu o banco OOT e nenhuma aprovação foi
  registrada pelo agente.
- A confiança foi removida dos escopos das issues #13, #16 e #22, conforme a
  decisão conversacional do usuário; a formalização D-020 segue pendente no
  fluxo de política.

## Tickets

| Ticket | Status nesta entrega | Registro |
| --- | --- | --- |
| #13 | Avaliação executada; publicação pendente (D-022) | D-019, D-020 e D-021 aprovadas pelo usuário às 12:13 UTC de 2026-10-30; fase `final_evaluation`; `avaliar-final` rodou uma vez (12:18 UTC). Resultados em `docs/relatorio/fase4/13-avaliacao-final.md` e `issues/13.md`. Publicação por série proposta como D-022. |
| #15 | Implementado (2026-10-30) | Decisão do usuário (2026-10-30): sem campo `quantidade`; contrato do #14 inalterado; critério de zero × ausente descartado. `POST /predicoes/lote`, `POST /predicoes/lote/xlsx` e template; 21 testes; suíte rápida 562 passaram (evidência `.ds-workflow/test-evidence/test-run-20261030T095901-1222695.json`). Detalhes em `issues/15.md`. |
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
- (Superado: o #13 produziu a avaliação descritiva no OOT; ver `issues/13.md`.)

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

## Mudança de escopo: pedidos novos e reajuste (2026-10-30)

- Pergunta do usuário: com pedidos novos (xlsx 1 e 2), é preciso reajustar para atualizar o gráfico com a previsão? Resposta dada: sim, o modelo ajustado não enxerga dados novos; só o reajuste muda a previsão.
- Decisão do usuário: o upload pela API dispara o reajuste. Contraria o ADR 0005 ("a API nunca treina"); por isso o `docs/adr/0011-atualizacao-de-dados-pela-api-com-reajuste.md` está **proposto**, não aprovado.
- Correção minha: antes eu havia dito que a predição não precisava mais de dados novos; estava errado quanto ao fluxo de dados, que o usuário corrigiu.
- Tickets abertos como `needs-info`, à espera do ADR: #28 (ingestão), #29 (reajuste), #30 (rota assíncrona), #31 (dashboard).
- Desvio do plano: o #26 e o README devem documentar o novo fluxo; o "treino real roda uma vez" vale para o treino com seleção do #12, não para o reajuste.

## Registro dos tickets #28 a #30 (ADR 0011, aprovado em 2026-10-30)

- Decisão do usuário: aprovou o ADR 0011 como proposto (promoção automática do `champion` à versão reajustada; antigo OOT como histórico no reajuste).
- Entregue: `atualizacao.py` (#28), `reajuste.py` (#29), rotas `POST /dados/pedidos` e `GET /dados/atualizacoes/{id}`, gerente em segundo plano e recarga do catálogo (#30), comando `reajustar`. Testes: `test_atualizacao.py` (14), `test_reajuste.py` (11), `test_api_atualizacao.py` (16). Suíte rápida: 541 passaram, 48 lentos fora (evidência `.ds-workflow/test-evidence/test-run-20261030T094959-1151433.json`).
- Desvios e achados: (1) o `GET /series` e a recomendação passaram a ler `db_path` (base completa), não a visão de desenvolvimento, porque o antigo OOT virou histórico; (2) o `GET /modelos` do #16 não mostrava o `champion` com o MLflow real (a busca de versões não devolve aliases), corrigido; (3) a refatoração tornou públicos `preparar_mlflow` e `config_intervalos` em `treino.py`.
- Hipótese não verificada: o reajuste de SARIMA e Prophet em dados reais pode levar minutos; só foi medido com séries sintéticas.
- #31 (dashboard) implementado: envio, erros, acompanhamento e gráfico atualizado; só `npm run build` verificado (sem fumaça com API real, para não gravar uma atualização na base real).
- Pendente: #24 (entrada manual e XLSX de predição no dashboard), #20 a #23, #25 e #26.

## Registro do #13

- Fatos: ver `docs/relatorio/fase4/13-avaliacao-final.md` (8 séries, MAE, RMSE, WAPE, MASE e cobertura 80/95%).
- Implementação: `src/case_mr_health/avaliacao_final.py`, comandos `avaliar-final` e `promover`, `tests/test_avaliacao_final.py` (26 testes).
- Integridade: a marca de tentativa fica em `.ds-workflow/final-evaluation-attempt.json` e não é apagada; uma nova execução recusa-se a abrir o OOT.
- Desvio do plano: o protocolo previa só o procedimento; os comandos foram escritos nesta sessão, com testes sobre OOT sintético, antes da execução real.
