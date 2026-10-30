# case-mr-health

Modelo preditivo da demanda dos SKUs `item A` a `item D` da MR. HEALTH, em
granularidade diária e semanal (8 séries, nível rede), com API (FastAPI),
rastreio e registro de modelos no MLflow e um dashboard em Svelte.

## Requisitos

- Python >= 3.14 e [uv](https://docs.astral.sh/uv/)
- Node.js e npm (só para o dashboard)

```bash
uv sync
(cd frontend && npm install)
```

## Clonar o repositório (demonstração)

Este é um repositório de **demonstração**. Para que o clone funcione sem
retreinar, o `data/mlflow/` (cerca de 80 MB: `mlflow.db` com o Model Registry
e os artefatos dos modelos) **está versionado**, junto com as planilhas em
`data/raw/`. Ele traz as 8 séries com o alias `champion` e todos os runs de
backtest e de avaliação final. Num projeto real, o registro de modelos ficaria
num servidor MLflow, fora do Git (veja "MLflow remoto" em Configuração).

Três ressalvas:

- **Caminhos absolutos.** O `mlflow.db` guarda os caminhos dos artefatos como
  `file:///home/rwallan/git/case-mr-health/...`. Se você clonar em outro
  diretório, reescreva-os uma vez, na raiz do clone (o `git status` passa a
  mostrar o `mlflow.db` modificado; não o commite). Sem isso, a API recusa os
  modelos (`modelo_indisponivel`). A correção automática é a issue #33.

  ```bash
  uv run python - <<'PY'
  import sqlite3
  from pathlib import Path

  antigo = 'file:///home/rwallan/git/case-mr-health'
  novo = Path.cwd().as_uri()
  con = sqlite3.connect('data/mlflow/mlflow.db')
  for tabela, coluna in [
      ('runs', 'artifact_uri'),
      ('logged_models', 'artifact_location'),
      ('experiments', 'artifact_location'),
      ('model_versions', 'storage_location'),
  ]:
      con.execute(
          f'update {tabela} set {coluna} = replace({coluna}, ?, ?)',
          (antigo, novo),
      )
  con.commit()
  PY
  ```

- **Bases do DuckDB não versionadas.** `data/processed/*.duckdb` e
  `data/servico/` são gerados: rode `uv run case-mr-health preparar-dados`
  antes de abrir o dashboard (a rota `/series` lê `base.duckdb`).
- **O retreino total não é repetível pelo CLI como está.** O `avaliar-final`
  abre o OOT uma única vez (marcador `.ds-workflow/final-evaluation-attempt.json`,
  versionado e já concluído) e, junto com o `promover`, depende de decisões
  aprovadas em `.ds-workflow/decisions.jsonl`. Os passos 2 e 3 abaixo
  descrevem o fluxo que gerou os modelos; a simplificação para quem quiser
  retreinar tudo está nas issues #34 a #36.

## Do zero ao dashboard

As planilhas brutas ficam em `data/raw/` (`PEDIDO-_1_.xlsx`,
`ITEM_PEDIDO-_2_.xlsx`, `ITENS-_3_.xlsx`).

1. **Preparar os dados.** Consolida as planilhas, gera o relatório de
   qualidade e separa o OOT (selado) da visão de desenvolvimento.

   ```bash
   uv run case-mr-health preparar-dados
   ```

2. **Treinar.** Backtest em origem móvel, candidatos e registro no MLflow das
   8 séries numa rodada. Imprime o identificador da rodada.

   ```bash
   uv run case-mr-health treinar --todas
   uv run case-mr-health selecionar --rodada <rodada>
   ```

3. **Avaliar e promover.** `avaliar-final` abre o OOT **uma única vez** e
   exige a fase e as decisões aprovadas; `promover` atribui o alias
   `champion` a uma versão avaliada, com a decisão de publicação do usuário.

   ```bash
   uv run case-mr-health avaliar-final
   uv run case-mr-health promover --sku A --granularidade diaria \
       --versao <n> --decisao <D-xxx>
   ```

   O `champion` das 8 séries já está promovido e versionado: **não repita
   os passos 2 e 3** só para subir o sistema (veja "Clonar o repositório").

4. **Subir a API** (porta 8000, um único worker). Swagger em
   `http://127.0.0.1:8000/docs`.

   ```bash
   uv run poe backend
   ```

5. **Subir a UI do MLflow** (porta 5000), apontando para o mesmo registro.

   ```bash
   uv run poe mlflow
   ```

6. **Abrir o dashboard** (porta 5173; veja `frontend/README.md`).

   ```bash
   uv run poe frontend
   ```

   `uv run poe frontend-build` (`npm run build`) gera `frontend/dist/` (verificação de compilação). O CORS
   da API só aceita o dashboard em `127.0.0.1:5173` e `localhost:5173`; para
   servir o build por outra porta, inclua-a em `src/case_mr_health/api/app.py`.

Para subir os três de uma vez (API, UI do MLflow e dashboard), use
`uv run poe app`; Ctrl+C encerra todos.

A API nunca treina: serve o `champion` de cada série. Se a base mudar, o
envio de pedidos novos pelo dashboard (`POST /dados/pedidos`) reajusta os
modelos em segundo plano (ADR 0011); `case-mr-health reajustar` recupera uma
atualização interrompida.

## Configuração

Tudo vem de `src/case_mr_health/config.py` e é sobrescrevível por variáveis
`CASE_MR_HEALTH_*` ou por um arquivo `.env`.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `CASE_MR_HEALTH_MLFLOW_TRACKING_URI` | `sqlite:///data/mlflow/mlflow.db` | Tracking e Model Registry |
| `CASE_MR_HEALTH_MLFLOW_ARTIFACT_DIR` | `data/mlflow/artefatos` | Artefatos dos modelos |
| `CASE_MR_HEALTH_HISTORICO_DB_PATH` | `data/servico/historico.duckdb` | Histórico de previsões servidas |
| `CASE_MR_HEALTH_API_HOST` / `_API_PORT` | `127.0.0.1` / `8000` | Endereço da API |
| `CASE_MR_HEALTH_MODELOS_FIXADOS` | vazio | Fixa versões (nome do modelo → versão) em vez do `champion` |
| `CASE_MR_HEALTH_LLM_API_KEY` / `_LLM_MODELO` | sem chave | Explicação por LLM; sem chave vale o template |

**MLflow remoto.** Basta trocar o URI, sem mudar código, por exemplo
`CASE_MR_HEALTH_MLFLOW_TRACKING_URI=http://servidor:5000`. Os artefatos
passam a ser guardados conforme o servidor.

**Endereços do dashboard.** O frontend lê `VITE_API_URL` (padrão
`http://localhost:8000`) e `VITE_MLFLOW_URL` (padrão `http://localhost:5000`;
é o destino do link para a UI do MLflow). Defina-os em
`frontend/.env.local`.

## Testes

```bash
uv run poe lint
uv run poe test-rapido   # sem os testes lentos (que treinam modelos)
```

`uv run poe test` roda também a suíte lenta; ela usa séries sintéticas e
MLflow temporário e não substitui o treino real.

## Limitações conhecidas

- **Histórico curto.** São cerca de 3 meses de pedidos: não há sazonalidade
  anual a aprender, a granularidade mensal não é servida (ADR 0001) e o
  horizonte validado é de no máximo 14 dias (ou 2 semanas) além do fim do
  treino.
- **Venda como proxy da demanda.** Só há vendas registradas; a demanda não
  atendida (ruptura) não é observada, então a previsão tende a subestimá-la.
- **Um único worker.** O DuckDB do histórico não aceita escrita concorrente
  de vários processos (ADR 0005); com uso real, o histórico precisaria migrar
  para um banco transacional. Só uma atualização de dados roda por vez.
- **Previsão da rede.** Não há previsão por unidade, e o valor unitário vem
  da configuração (`valores_unitarios`).
- **LLM.** A explicação com LLM real não foi exercitada neste projeto; sem
  chave, o texto vem do template determinístico.
