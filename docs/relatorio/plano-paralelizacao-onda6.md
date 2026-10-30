# Plano de paralelização das issues #38 a #51 (proposta)

Status: **PROPOSTA**, aguarda decisão do usuário. Nada foi disparado em paralelo. Base: campos `Blocked by:` de `issues/38.md` a `issues/51.md` em 2026-10-30. Complementa `docs/relatorio/registro-onda6.md`; segue o formato de `docs/relatorio/plano-paralelizacao.md`.

## 1. Grafo de dependências

```
#39 ──► #40 ──► #41 ──┐
                      ├─► #48 ──┐
#42 ──┬─► #43 ──► #45 ┘         │
      ├─► #44                   │
      ├─► #46                   ├─► #51
      └─► #47 ──┬─► #48 ◄── #41 │
                ├─► #49 ────────┤
                └─► #50 ────────┘
#38 ────────────────────────────┘
```

Mais precisamente: #40 depende de #39; #41 de #39 e #40; #43, #44, #46 e #47 de #42; #45 de #42 e #43; #48 de #47 e #41; #49 e #50 de #47; #51 de #38, #41, #43, #44, #45, #46, #48, #49 e #50. Sem bloqueio: #38, #39 e #42.

## 2. Ondas

| Onda | Tickets (em paralelo) | Pré-requisito | Observações |
| --- | --- | --- | --- |
| 0 (agora) | Aprovação do usuário para o reajuste real do #40 | — | É decisão, não código: o reajuste altera `data/mlflow` versionado. Pedir antes, para não travar a onda 2. |
| 1 | #38, #39, #42 | nenhum | Três frentes independentes: gráfico (frontend), contrato da API (backend), tokens (frontend). |
| 2 | #40, #43, #44, #46, #47 | #39 (#40); #42 (os demais) | Cinco frentes: reajuste operacional, upload, LLM, changelog no app, MkDocs. |
| 3 | #41, #49, #50 | #39 e #40 (#41); #47 (#49, #50) | Formulário e as duas páginas de documentação que não dependem de tela. |
| 4 | #45, #48 | #42 e #43 (#45); #47 e #41 (#48) | Acessibilidade varre o frontend inteiro, então vem depois das telas; #48 descreve o fluxo final. |
| 5 | #51 | #38 a #50 | Revisão final e fechamento do registro. |

Antecipação possível, com baixo custo: **escrever o texto** de #48, #49 e #50 (Markdown em `docs/guia/`) já na onda 1 ou 2, porque as fontes são código e ADRs existentes e não dependem de código novo. O que depende de #47 é só o build do site e o link; o texto de #48 que descreve o formulário final espera #41. Só vale se o arquivo de navegação (`mkdocs.yml`) não for editado por esses agentes (ver seção 4).

## 3. O que NÃO paraleliza (gargalo real)

- **#40 (reajuste):** serializado. O MLflow em SQLite aceita um escritor; o reajuste de SARIMA e Prophet é lento; e ele altera `data/mlflow`. Nenhum outro agente pode rodar a API, testes que carreguem o registro real ou outro reajuste ao mesmo tempo. Antes dele, nenhum critério de #41 que dependa de "previsão no futuro real" pode ser verificado.
- **Aprovação do usuário** para o reajuste (#40) e para a escolha de limites de upload e de ferramenta de acessibilidade (#43, #45): agrupar os pedidos.
- **Verificação visual em navegador:** é do usuário (como na #26) e fica para o fim de cada onda de frontend, em lote.
- **#51:** sequencial por natureza.

## 4. Pontos de conflito e como evitá-los

A maior colisão é no frontend: `App.svelte` é tocado por #38, #41, #42, #43, #45, #46 e #47; `style.css`, por #38 e #42; `LinksApi.svelte`, por #46 e #47.

- **`App.svelte` (309 linhas):** cada ticket tira a sua parte para um componente próprio e deixa em `App.svelte` só o ponto de uso. #38 cria `GraficoPrevisao.svelte` e `grafico.js` (montagem da série e regra do zero), sem editar CSS global. #43 cria `Upload.svelte`. #41 cria `FormularioPrevisao.svelte`. #46 cria `Changelog.svelte` e um ponto de rota mínimo.
- **`style.css`:** #42 é o único dono da troca por variáveis. #38 escreve os estilos do gráfico dentro do componente (`<style>` do Svelte) usando, na leitura, os nomes de token definidos em `design/tokens.css`; se #38 mesclar antes de #42, os tokens ainda não existem, então #42 mescla primeiro (ordem abaixo).
- **`LinksApi.svelte` (#46, #47):** #47 só acrescenta o link da documentação; #46 só troca o destino do changelog. Mesclar #46 e depois #47, com rebase trivial.
- **`EntradaPrevisoes.svelte`:** #43 (upload) na onda 2, #41 (formulário) na onda 3, #45 na onda 4. A ordem sequencial já evita o conflito.
- **`pyproject.toml` e `uv.lock`:** só #47 acrescenta dependências (grupo `docs`) e tarefas poe. `uv.lock` já aparece modificado no `git status` do início da onda: resolver antes de abrir os worktrees (decisão do usuário).
- **`mkdocs.yml`:** #47 cria o esqueleto com `nav` completo e páginas vazias de #48 a #50. Cada agente de documentação edita só os seus arquivos Markdown. Sem isso, os três conflitariam no `nav`.
- **`docs/relatorio/registro-onda6.md`:** arquivo único. Cada agente escreve o seu bloco em `docs/relatorio/onda6/<ID>.md`; quem integra consolida no registro.
- **Backend:** #39 toca `schemas/predicao.py`, `servicos/predicao.py`, `schemas/lote.py`, `servicos/lote.py` e o template XLSX; nenhum outro ticket toca esses arquivos. #44 toca `explicacao.py` e `rotas/recomendacoes.py` só se a auditoria achar vazamento.
- **`frontend/node_modules` está versionado** (aparece em `git ls-files`): nenhum agente deve rodar `npm install` nem alterar `package.json`; se um ticket precisar de dependência nova, parar e perguntar ao usuário.
- **`CHANGELOG`:** um fragmento por ticket (`<ID>.<tipo>.md`), sem conflito.
- **Sem treino** em nenhum ticket (regra do projeto, `project_suite_lenta_apos_vencedor`): só `uv run poe lint` e `uv run poe test-rapido`. O reajuste do #40 não é treino, mas é lento e de uso exclusivo.

## 5. Mecânica proposta

- Uma branch e um worktree por ticket (`<ID>-<titulo_breve>`, conforme `CLAUDE.md`), a partir de `main`; os tickets das ondas 2 em diante partem da base de integração que já contém as ondas anteriores. Cada agente entrega: código, testes (rápidos), fragmento de changelog, `## Answer` na issue, bloco de registro em `docs/relatorio/onda6/<ID>.md` e lint verde.
- **Ordem de integração dentro de cada onda:** onda 1: #42, #39, #38. Onda 2: #40 (isolado, sem outros agentes usando o registro), #46, #47, #43, #44. Onda 3: #41, #49, #50. Onda 4: #48, #45. Teste rápido na base de integração após cada merge.
- Integração por **pull request**, aprovada e mesclada pelo GitHub (memória do projeto `feedback_integrar_via_pr`); commits sem coautoria do Claude (`CLAUDE.md`).
- Sem teste automatizado de frontend no projeto: cada agente de frontend entrega, no `## Answer`, um roteiro curto de verificação visual para o usuário rodar no fim da onda (`uv run poe app`).
- Decisões novas que surgirem em um ticket são propostas ao usuário e aprovadas em lote; nenhuma vira ADR sem os três critérios (difícil de reverter, surpreendente, com troca real).

## 6. Ganho esperado (estimativa qualitativa, não medida)

São 14 tickets e a cadeia mais longa é #39 → #40 → #41 → #48 → #51 (5 etapas). Em ondas, a execução cai de 14 etapas sequenciais para 5 ondas, com 3 a 5 agentes simultâneos nas ondas 1 a 3. O ganho é limitado pela aprovação do reajuste, pelo uso exclusivo do registro MLflow no #40 e pela colisão em `App.svelte`, mitigada pela extração em componentes.

## 7. Pendências deste plano

- O número de agentes simultâneos e o uso de worktrees não foram decididos pelo usuário.
- O estado do `uv.lock` modificado precisa ser resolvido antes de abrir os worktrees.
- Se #38 precisar do tema de tokens antes de #42 mesclar, a ordem da onda 1 muda para #42 primeiro; a tabela já assume isso.
