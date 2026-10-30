# Retreino e troubleshooting

## Dois caminhos

**Só subir o sistema.** Use o que está versionado: `data/mlflow/` já tem o
`champion` das 8 séries. Rode `preparar-dados` e depois `uv run poe app`
(veja [execução](execucao.md)). Não repita o treino.

**Dados novos.** Pelo dashboard (seção "Enviar pedidos novos") ou por
`POST /dados/pedidos`: valida as duas planilhas, atualiza a base e reajusta
os modelos em segundo plano, uma atualização por vez (ADR 0011). O
reajuste mantém o algoritmo e os hiperparâmetros de cada versão servida, não
reseleciona o modelo, e cada série passa a servir a versão nova quando
termina. Versões reajustadas não têm métrica fora da amostra. Acompanhe em
`GET /dados/atualizacoes/{id}`.

**Recuperação.** Se a API caiu no meio de uma atualização:

```bash
uv run case-mr-health reajustar    # não verificado: escreve em data/mlflow
```

Cada série com falha é relatada e as demais seguem; o comando sai com 1 se
alguma falhou.

## Retreino total

Os comandos existem separadamente, mas o encadeamento num só comando
(`case-mr-health retreinar` e os atalhos `poe preparar`, `treinar` e
`selecionar`, issue #35) **ainda não existe**, e o guia de retreino (#36) está
pendente. O fluxo que gerou os modelos é:

```bash
uv run case-mr-health preparar-dados
uv run case-mr-health treinar --todas          # imprime a rodada
uv run case-mr-health selecionar --rodada <rodada>
uv run case-mr-health avaliar-final
uv run case-mr-health promover --sku A --granularidade diaria --versao <n> --decisao <D-xxx>
```

Todos **não verificados** nesta página (treinam ou escrevem em `data/mlflow`).
Cuidados, a partir do código e do README:

- O treino das 8 séries é longo (SARIMA, Prophet e intervalos por origem
  móvel) e cria versões novas no registro, sem apagar as atuais.
- `avaliar-final` abre o OOT uma única vez, depende de decisões aprovadas e
  não pode ser repetido neste repositório (o marcador de tentativa já está
  versionado). Por isso o retreino total não é repetível pelo CLI como está.
  Uma reavaliação no OOT já visto não é estimativa independente (ADR 0012).
- Para voltar ao `champion` versionado: `git checkout -- data/mlflow`
  (proposta do #36; não verificada).

## Manutenção

- **Versões.** Semantic Versioning por `towncrier`; os fragmentos ficam em
  `changelogs/`. A API lê o `CHANGELOG.md` (`GET /changelog`).
- **Dados gerados.** `data/processed/`, `data/servico/` e
  `data/atualizacoes/` são regeneráveis e não versionados. `data/mlflow/` é
  versionado nesta demonstração (cerca de 80 MB).
- **Histórico de previsões.** DuckDB em `data/servico/historico.duckdb`, um
  único escritor (um worker); com uso real, precisaria de banco transacional.
- **Documentação.** `uv run poe docs-build` falha (`--strict`) em link
  quebrado.
- **Qualidade.** `uv run poe lint` e `uv run poe test-rapido` antes de
  integrar.

## Troubleshooting

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| `modelo_indisponivel` (503) em todas as séries após clonar | Caminhos absolutos no `mlflow.db` | Reescrever os caminhos (README, "Clonar o repositório"); #33 |
| `modelo_indisponivel` em uma série | Sem alias `champion` nem versão fixada | Ver `GET /modelos`; promover ou fixar via `CASE_MR_HEALTH_MODELOS_FIXADOS` |
| `historico_indisponivel` em `/series` | `base.duckdb` ausente | `case-mr-health preparar-dados` |
| Dashboard sem dados, erro de CORS no navegador | Origem diferente de `localhost:5173` ou `127.0.0.1:5173` | Usar essas origens ou alterar `api/app.py` |
| Dashboard aponta para a API errada | `VITE_API_URL` | `frontend/.env.local` e reiniciar o Vite |
| 409 `atualizacao_recusada` | Outra atualização em andamento, ou o par já aplicado | Aguardar o fim; não reenviar o mesmo par |
| 404 em `/dados/atualizacoes/{id}` | A API reiniciou (estado só em memória) | Consultar `/series` e `/modelos`; se preciso, `reajustar` |
| 422 `dados_invalidos` | Planilha fora das regras | Ler `detalhes` (planilha e linha); nada foi aplicado |
| `horizonte_acima_do_limite` | Previsão além de 14 dias ou 2 semanas do fim do treino | Reduzir o horizonte ou a data de referência |
| Explicação em texto fixo | Sem `CASE_MR_HEALTH_LLM_API_KEY` | Esperado: vale o template; a chamada real a um LLM não foi exercitada |
| Erro de lock no DuckDB | Dois processos escrevendo | Manter um único worker e uma API por base |
| `--strict` falha no MkDocs | Link ou nav quebrados | Ler a mensagem; corrigir o Markdown |

## Lacunas

- **Docker e Docker Compose**: não há Dockerfile nem Compose versionados.
  Não existe procedimento de build de imagem.
- **Deploy**: não há procedimento de publicação, servidor, proxy, TLS,
  autenticação nem monitoramento. A API é local (`127.0.0.1`), sem
  autenticação.
- **Publicação desta documentação** (GitHub Pages ou outra): sem destino.
- **Retreino em um comando** (#35) e correção dos caminhos do MLflow (#33):
  não entregues.
- **Execução do sistema**: nesta página, servidores, treino, reajuste e
  `npm install` não foram executados; ver a coluna "Status" em
  [execução](execucao.md).
