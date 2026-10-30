# Execução, testes e logs

## Execução local

As tarefas são do `poethepoet` (`uv run poe <tarefa>`).

| Tarefa | O que faz | Endereço | Status |
| --- | --- | --- | --- |
| `backend` | `case-mr-health servir`: API com **um único worker** (ADR 0005) | `http://127.0.0.1:8000` | Não verificado (sobe servidor) |
| `mlflow` | UI do MLflow sobre `data/mlflow/mlflow.db` | `http://127.0.0.1:5000` | Não verificado |
| `frontend` | `npm run dev` (Vite) | `http://127.0.0.1:5173` | Não verificado |
| `frontend-build` | `npm run build`, gera `frontend/dist/` | | Não verificado no worktree (ver registro) |
| `docs` | `mkdocs serve` | `http://127.0.0.1:8001` | Não verificado |
| `docs-build` | `mkdocs build --strict` | `site/` | Verificado |
| `parar` | `scripts/parar_app.py`: encerra (SIGKILL) quem escuta nas portas 8000, 5000, 5173 e 8001 | | Verificado na porta 8000 |
| `app` | `parar` e depois `backend`, `mlflow`, `frontend` e `docs` em paralelo; Ctrl+C encerra todos | | Não verificado |

```bash
uv run poe app
```

A API carrega os modelos `champion` na inicialização. Para trocar host ou
porta: `uv run case-mr-health servir --host 127.0.0.1 --porta 8000`
(verificado só o `--help`). A API nunca treina numa requisição de predição; o
envio de pedidos novos reajusta os modelos em segundo plano (ADR 0011, ver
[retreino](retreino-e-troubleshooting.md)).

Antes da primeira execução rode `preparar-dados`: a rota `/series` lê
`data/processed/base.duckdb`, que não é versionado.

## Comandos da CLI

Verificado: `uv run case-mr-health --help` e o `--help` de cada comando.

| Comando | Função | Observação |
| --- | --- | --- |
| `preparar-dados` | Consolida planilhas, gera o relatório e separa o OOT | Escreve em `data/processed` |
| `treinar` | `--todas`, ou `--sku` com `--granularidade`; `--seed` | Registra no MLflow; longo |
| `selecionar` | `--rodada <id>`; `--resumo-path` | Publica a seleção |
| `servir` | `--host`, `--porta` | Um worker |
| `avaliar-final` | Abre o OOT **uma única vez** | Exige decisões aprovadas; não repetível |
| `promover` | `--sku --granularidade --versao --decisao` | Atribui o alias `champion` |
| `reajustar` | Reajusta as 8 séries na base atual | Recuperação (ADR 0011) |

Os comandos retornam 0 em sucesso e 1 em erro de uso ou de dados (a causa vai
para o log).

## Testes

| Comando | O que roda | Status |
| --- | --- | --- |
| `uv run poe lint` | `ruff check` | Verificado |
| `uv run poe test-frontend` | `node --test` sobre `frontend/src/*.test.js` (23 testes) | Verificado: todos passam |
| `uv run poe test-rapido` | `pytest -m 'not lento'` | Não rodado nesta entrega (sem mudança de backend) |
| `uv run poe test` | lint, a suíte completa com cobertura e relatório HTML | Não verificado; inclui os testes lentos |
| `uv run pytest tests/arquivo.py::teste` | Um teste | Não verificado |

Os testes usam séries sintéticas (`faker`) e MLflow temporário; nenhum treina
sobre os dados reais. Depois da escolha do modelo (#12), a suíte lenta só se
justifica ao mexer em treino ou seleção.

## Logs

Os logs usam `loguru` e vão para o `stderr` do processo (`logs.configurar_logs`),
sem arquivo nem rotação. O nível vem de `CASE_MR_HEALTH_LOG_LEVEL` (padrão
`INFO`). Para guardar, redirecione a saída (`... 2> api.log`). O `uvicorn`
escreve o próprio log de acesso. Não há agregador de logs.

## Swagger e OpenAPI

Com a API no ar:

| Endereço | O que é |
| --- | --- |
| `http://127.0.0.1:8000/docs` | Swagger UI (testar as rotas no navegador) |
| `http://127.0.0.1:8000/redoc` | ReDoc |
| `http://127.0.0.1:8000/openapi.json` | Contrato OpenAPI para clientes |

Verificado com `TestClient` (leitura, sem subir servidor): `/openapi.json`,
`/docs` e `/redoc` respondem 200; versão `0.5.0`, 13 rotas e 30 schemas.
No Swagger, use "Try it out". A API só expõe rotas `GET` e `POST`.

### Rotas e códigos HTTP

Todo erro de negócio vem em `ErroResposta`:
`{"codigo": ..., "mensagem": ..., "detalhes": [{"campo": ..., "mensagem": ...}]}`.

| Rota | Função | Códigos documentados |
| --- | --- | --- |
| `POST /predicoes` | Previsão da rede de um SKU (`sku`, `granularidade`, `horizonte`, `data_referencia` opcional) | 200, 404, 422, 503 |
| `POST /predicoes/lote` | Várias combinações, tudo ou nada | 200, 422, 503 |
| `POST /predicoes/lote/xlsx` | O mesmo, por planilha | 200, 422, 503 |
| `GET /predicoes/lote/template.xlsx` | Template da planilha | 200 |
| `GET /previsoes` | Previsões já servidas (`sku`, `granularidade`, `limite` 1 a 500, `deslocamento`) | 200, 422, 503 (404 existe no código; ver divergências) |
| `GET /previsoes/exportacao.xlsx` | Exporta o histórico filtrado | 200, 422, 503 (idem) |
| `GET /modelos` | Versões e aliases no Registry | 200, 503 |
| `GET /series/{sku}/{granularidade}` | Série de vendas da rede | 200, 404, 422, 503 |
| `GET /recomendacoes/{sku}` | Recomendação de estoque | 200, 404, 422, 503 |
| `POST /alertas/email` | Alerta de e-mail **simulado**; nada é enviado | 200, 404, 422, 503 |
| `POST /dados/pedidos` | Envia duas planilhas (`pedidos`, `itens`) e reajusta | 202, 409, 422 |
| `GET /dados/atualizacoes/{id}` | Estado do reajuste | 200, 404, 422 |
| `GET /changelog` | Changelog estruturado | 200 |

Significado dos códigos de negócio (`src/case_mr_health/api/erros.py`):

| `codigo` | HTTP | Quando |
| --- | --- | --- |
| `requisicao_invalida` | 422 | Fora do contrato de entrada (campo ausente, tipo, enumeração) |
| `data_referencia_invalida`, `horizonte_acima_do_limite` | 422 | Data antes do treino; horizonte além do máximo validado (14 dias ou 2 semanas) |
| `dados_invalidos` | 422 | Planilhas de `POST /dados/pedidos` reprovadas; traz planilha e linha |
| `lote_invalido` | 422 | Item ou linha inválida no lote |
| `sku_inexistente` | 404 | SKU fora de `item A` a `item D` |
| `atualizacao_inexistente` | 404 | Id desconhecido (o estado só vive enquanto a API está de pé) |
| `atualizacao_recusada` | 409 | Já há atualização em andamento, ou o par já foi aplicado |
| `modelo_indisponivel`, `historico_indisponivel` | 503 | Sem `champion` nem versão fixada, ou base ausente |

Exemplo (verificado contra `PedidoPredicao`, rejeitado com 422 sem tocar nos
modelos): `POST /predicoes` com `{"sku": "A"}` responde
`requisicao_invalida` com o detalhe `granularidade: campo obrigatório ausente`.
Exemplo de corpo válido, do próprio schema (a resposta não foi exercida, pois
exige os modelos carregados): `{"sku": "item A", "granularidade": "diaria", "horizonte": 3}`.

### Divergências entre o Swagger e o código

A conferência feita nesta entrega está em `docs/relatorio/onda6/50.md`. Em
resumo, o Swagger descreve o 422 de validação do FastAPI
(`HTTPValidationError`) em rotas com parâmetros, mas o corpo real é o
`ErroResposta`; `GET /previsoes` e `/previsoes/exportacao.xlsx` não declaram
o 404 que o código pode devolver; e a mensagem de `greater_than_equal` é
fixa em "maior ou igual a 1", mesmo para `deslocamento` (mínimo 0), e o
limite máximo de `limite` (500) sai em inglês.
