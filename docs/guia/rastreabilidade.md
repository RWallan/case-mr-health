# Rastreabilidade

Esta página registra diferenças conhecidas entre decisões/planos anteriores e o comportamento atual. O código e os testes são a referência para o comportamento vigente; divergências não foram alteradas silenciosamente nesta revisão.

| Tema | Situação | Documentação e evidência |
| --- | --- | --- |
| Uma versão de modelo por SKU e granularidade | Implementado | [Reajuste e avaliação final](ciencia-de-dados/reajuste-e-avaliacao.md); `api/modelos.py`, `api/mlflow_cliente.py`, `treino.py`; testes `tests/test_api_predicao.py`. |
| Métricas finais no OOT e seleção por backtest | Implementado e reportado | [Reajuste e avaliação final](ciencia-de-dados/reajuste-e-avaliacao.md), [Seleção e intervalos](ciencia-de-dados/selecao-e-intervalos.md); relatórios `docs/relatorio/fase2/12-resumo.md` e `docs/relatorio/fase4/13-avaliacao-final.md`. |
| Confiança derivada de MASE | Substituída/removida do fluxo atual | ADR 0008 e D-020; não há módulo/configuração de confiança ativo. Persistem tags históricas em versões MLflow e campo opcional na explicação (`api/servicos/explicacao.py`); pendência de limpeza/decisão em `docs/relatorio/onda6/49.md`. |
| ARIMA e Prophet como candidatos | Decisão anterior substituída por corte de 2026-10-30 | ADRs 0003 e 0010 ainda descrevem candidatos; `candidatos.py` os exclui conforme o registro de #49. Não foi criado ADR para a emenda; precisa formalização. |
| Reavaliação `--demonstracao` | Documentado no ADR 0012, mas não implementado | Não há opção no código; issues #35 e #37 permanecem pendentes conforme `docs/relatorio/onda6/49.md`. |
| Identificação do conjunto reajustado | Lacuna conhecida | Tag `hash_dados = base` não identifica um hash da base; registrado em `docs/relatorio/onda6/49.md`. |
| Swagger e contratos de erro | Divergências observadas, não corrigidas | `docs/relatorio/onda6/50.md` lista 422 descrito como `HTTPValidationError` embora o corpo use `ErroResposta`; 404 não declarado em duas rotas; mensagens de limites inconsistentes e fallback 404 padrão do FastAPI. Conferir `/docs` para o contrato publicado. |
| Previsão com referência automática | Implementada segundo ADR 0013 | Sem data, o serviço escolhe referência compatível com a versão do modelo; comprovado no registro de #41 e em `api/servicos/predicao.py`. |
| Previsão zero e plot por data | Implementado no frontend | Issue #38 e `frontend/src/GraficoPrevisao.svelte`, `AvisoZero.svelte`; testes de módulo, sem validação visual no navegador. |
| Alerta por e-mail | Demonstração mockada | Issue #21 e serviço de alertas; não há envio externo nem garantia de entrega. |

## Itens implementados

A separação frontend/API, modelos servidos pelo MLflow, histórico DuckDB, entradas manual e XLSX, lote, comparação, changelog, acessibilidade e documentação são descritos nas páginas deste guia com fontes no código e nos testes.

## Itens não implementados ou pendentes

- Envio real de e-mail; deploy, TLS, autenticação e monitoramento operacional.
- Comando de retreino único e opção `--demonstracao` (issues #35 e #37).
- Formalização da retirada de ARIMA/Prophet e decisão sobre tags/campo histórico de confiança.
- Correção das divergências do Swagger (issue nova necessária, conforme registro #50).
- Validação visual dos fluxos em navegador; os critérios de interface foram verificados por código e testes automatizados.
