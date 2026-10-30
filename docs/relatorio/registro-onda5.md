# Registro da Onda 5 — verificação do sistema integrado (#26)

Data: 2026-10-30  
Escopo: issue #26, conforme `docs/relatorio/plano-paralelizacao.md`. A onda
tem um único ticket (todos os bloqueios #13, #23, #24 e #25 estão
`resolved`), então não há o que paralelizar. Nenhuma skill específica se
aplicou: não houve treino, modelagem nem bug a diagnosticar.

## Ticket

| Ticket | Branch | Status | Entrega |
| --- | --- | --- | --- |
| #26 | `26-verificacao_sistema` | `resolved` | `README.md`, passada de fumaça, `changelogs/26.interno.md` |

## Passada de fumaça (sem retreinar, `champion` já promovido)

Estado de partida: as 8 séries têm alias `champion` no MLflow
(`sqlite:///data/mlflow/mlflow.db`; versões 6, 4, 17, 4, 5, 4, 9, 4 para
A-diária, A-semanal, B-diária, B-semanal, C-diária, C-semanal, D-diária,
D-semanal). Histórico de previsões isolado em arquivo temporário
(`CASE_MR_HEALTH_HISTORICO_DB_PATH`), para não poluir `data/servico/`.

| Passo | Comando | Resultado |
| --- | --- | --- |
| API | `uv run case-mr-health servir` | sobe; `GET /openapi.json` 200 |
| UI do MLflow | `uv run mlflow ui --backend-store-uri sqlite:///data/mlflow/mlflow.db --port 5000` | `/health` OK; `/` 200 |
| Predição | `POST /predicoes` (`item A`, diária, `2021-08-19`, horizonte 3) | 200; 3 períodos, versão 6, intervalos 80% e 95% |
| Consultas | `GET /previsoes?limite=1`, `/recomendacoes/A`, `/series/A/semanal`, `/modelos` | 200 em todas |
| CORS | `Origin: http://127.0.0.1:5173` em `/modelos` | `access-control-allow-origin` devolvido |
| Build | `npm run build` (`frontend/`) | sem erros; JS 70,10 kB, CSS 10,40 kB |
| Página | `npm run preview` e `GET /` | 200, HTML com `<title>Previsão de demanda | MR. HEALTH</title>` |

Suíte: `uv run poe lint` limpo; `uv run poe test-rapido` 632 passaram, 48
lentos excluídos (187 s). Nenhum treino rodou.

## Limitações da verificação

- O dashboard **não foi aberto num navegador**: a página foi verificada só
  por HTTP (HTML servido e chamadas da API). A verificação visual cabe ao
  usuário (decisão de 2026-10-30, sem Playwright).
- `GET /recomendacoes` (sem SKU) responde 404: a rota é por SKU; não é falha.
- O `preview` do Vite (porta 4173) não está nas origens do CORS; um navegador
  bloquearia as chamadas dele à API. Documentado no README; a tela deve ser
  vista por `npm run dev` (5173).
- A explicação com LLM real e o e-mail não foram exercitados.

## Pendências

- Processos da passada de fumaça (API na 8000, UI do MLflow na 5000) foram encerrados depois; as portas ficaram livres.
- Sugestão (CLAUDE.md): fechar o marco com `uv version` e `towncrier build`.
  Fragmentos pendentes incluem `adicionado`, portanto MINOR (0.5.0), a
  confirmar com o usuário.

## Pós-onda: MLflow versionado e retreino por humanos (2026-10-30)

Pergunta do usuário: o clone traz os artefatos do MLflow e o modelo selecionado? Resposta verificada: não, `data/mlflow/`, `data/processed/` e `*.duckdb` estão no `.gitignore`; sem `champion`, a API responde 503. O `.ds-workflow/` **é** versionado, e `avaliar-final`/`promover` o leem (fase, protocolo congelado, decisões aprovadas, marcador de tentativa única já `concluida`), então o CLI não refaz a avaliação final no clone.

Decisão do usuário: opção 1, versionar o `data/mlflow/` (repositório de demonstração; issue #32, resolvida). Achado: o `mlflow.db` tem caminhos absolutos; sem reescrevê-los, o clone em outro diretório recebe 503 (hash vazio), e com a reescrita a predição devolve a mesma versão e o mesmo hash (teste em cópia, fora do repositório). Issues abertas a pedido do usuário para simplificar o retreino total por humanos: #33 (relocar o MLflow), #34 (avaliação final e promoção sem o agente; exige decisão), #35 (comando `retreinar`), #36 (guia e README). Nada disso foi implementado nesta etapa.
