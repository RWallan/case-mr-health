# Instalação e configuração

## Pré-requisitos

| Item | Versão | Uso |
| --- | --- | --- |
| Python | >= 3.14 | Backend e CLI (`pyproject.toml`) |
| [uv](https://docs.astral.sh/uv/) | recente | Ambiente e tarefas |
| Node.js e npm | recentes | Só o dashboard (Svelte e Vite) |

O projeto não fixa a versão do Node. Na verificação desta página foram usados
Python 3.14.0, Node v26.12.1 e npm 12.2.1.

## Instalação

```bash
uv sync                          # backend, grupo dev (não verificado: o ambiente já existia)
uv sync --group docs             # só se for servir esta documentação
(cd frontend && npm install)     # não verificado
```

As planilhas brutas (`data/raw/`) e o registro de modelos (`data/mlflow/`)
estão versionados, então um clone já tem o que a API precisa, exceto as bases
DuckDB, que são geradas:

```bash
uv run case-mr-health preparar-dados   # não verificado: escreve em data/processed
```

!!! warning "Caminhos absolutos no MLflow"
    O `data/mlflow/mlflow.db` guarda caminhos absolutos de artefatos do
    computador de origem. Clonado em outro diretório, a API responde
    `modelo_indisponivel` até que os caminhos sejam reescritos (script no
    `README.md`, seção "Clonar o repositório"). A correção automática é a
    issue #33, ainda não entregue.

## Configuração do backend

A configuração é a classe `Settings` (`src/case_mr_health/config.py`, pydantic
settings). Cada campo vira uma variável `CASE_MR_HEALTH_<CAMPO>` (maiúsculas),
lida do ambiente ou de um arquivo `.env` na raiz de onde o comando roda. O
repositório não traz `.env`; crie-o se precisar. Variáveis desconhecidas são
ignoradas.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `CASE_MR_HEALTH_RAW_DIR` | `data/raw` | Planilhas brutas |
| `CASE_MR_HEALTH_DB_PATH` | `data/processed/base.duckdb` | Base consolidada (selada) |
| `CASE_MR_HEALTH_DESENVOLVIMENTO_DB_PATH` / `_OOT_DB_PATH` | `data/processed/desenvolvimento.duckdb` / `oot.duckdb` | Visão de desenvolvimento e OOT selado |
| `CASE_MR_HEALTH_RELATORIO_PATH` | `data/processed/relatorio_qualidade.md` | Relatório de qualidade |
| `CASE_MR_HEALTH_MLFLOW_TRACKING_URI` | `sqlite:///data/mlflow/mlflow.db` | Tracking e Model Registry |
| `CASE_MR_HEALTH_MLFLOW_ARTIFACT_DIR` | `data/mlflow/artefatos` | Artefatos dos modelos |
| `CASE_MR_HEALTH_HISTORICO_DB_PATH` | `data/servico/historico.duckdb` | Histórico de previsões servidas |
| `CASE_MR_HEALTH_ATUALIZACOES_DIR` | `data/atualizacoes` | Cópia das planilhas aplicadas |
| `CASE_MR_HEALTH_CHANGELOG_PATH` | `CHANGELOG.md` | Fonte de `GET /changelog` |
| `CASE_MR_HEALTH_API_HOST` / `_API_PORT` | `127.0.0.1` / `8000` | Endereço da API |
| `CASE_MR_HEALTH_LOG_LEVEL` | `INFO` | Nível dos logs |
| `CASE_MR_HEALTH_SEED` | vazio (data local `AAAAMMDD`) | Seed do treino |
| `CASE_MR_HEALTH_MODELOS_FIXADOS` | `{}` | Fixa versões em vez do `champion` |
| `CASE_MR_HEALTH_VALORES_UNITARIOS` | itens A a D: 10, 15, 20, 25 | Valor unitário usado nas recomendações |
| `CASE_MR_HEALTH_LLM_API_KEY` | sem chave | Explicação por LLM; sem chave vale o template |
| `CASE_MR_HEALTH_LLM_MODELO` / `_LLM_TIMEOUT_S` / `_LLM_MAX_TOKENS` | `claude-sonnet-5-5` / `20.0` / `600` | Parâmetros do LLM |

Existem ainda os parâmetros metodológicos (partições, treino mínimo, níveis
dos intervalos, `INTERVALO_MAX_ORIGENS`); veja `config.py` e as páginas de
[ciência de dados](../ciencia-de-dados/index.md). Não os altere em operação:
mudam o resultado do treino.

Valores estruturados (dicionários e tuplas) entram como JSON. Verificado:

```bash
CASE_MR_HEALTH_MODELOS_FIXADOS='{"demanda-item-a-diaria":"3"}' \
CASE_MR_HEALTH_LOG_LEVEL=DEBUG CASE_MR_HEALTH_API_PORT=9000 uv run ...
```

lê `modelos_fixados={'demanda-item-a-diaria': '3'}`, nível `DEBUG` e porta
`9000`. Os nomes de modelo têm a forma `demanda-item-<x>-<granularidade>`
(ex.: `demanda-item-c-semanal`).

**MLflow remoto.** Troque só o URI: `CASE_MR_HEALTH_MLFLOW_TRACKING_URI=http://servidor:5000`
(não verificado). Os artefatos passam a seguir o servidor.

## Configuração do frontend

O dashboard lê variáveis `VITE_*` em tempo de build ou de `npm run dev`.
Defina-as em `frontend/.env.local` (não versionado):

| Variável | Padrão | Uso |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000` | Base da API |
| `VITE_MLFLOW_URL` | `http://localhost:5000` | Link para a UI do MLflow |
| `VITE_DOCS_URL` | `http://localhost:8001` | Link "Documentação" |

O CORS da API aceita só `http://localhost:5173` e `http://127.0.0.1:5173`, e
só os métodos `GET` e `POST` (`src/case_mr_health/api/app.py`). Servir o
dashboard por outra origem exige alterar esse arquivo.
