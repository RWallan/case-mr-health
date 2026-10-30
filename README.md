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

   Neste repositório, o `champion` das 8 séries já está promovido: **não
   repita os passos 2 e 3** só para subir o sistema.

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
