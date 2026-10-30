# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão geral

Projeto de **ciência de dados**: modelo preditivo para prever demanda futura. Pacote Python em layout `src/` (`src/case_mr_health/`), gerenciado com `uv`, Python >= 3.14.

Stack principal (ver `pyproject.toml`): pandas, duckdb, scikit-learn, feature-engine, mlflow (rastreio de experimentos), FastAPI (servir o modelo), cyclopts (CLI), pydantic-settings (configuração), loguru (logging), openpyxl (leitura de Excel). Em dev: notebook, faker (dados sintéticos para testes), pytest.

O entrypoint de CLI é `case-mr-health` → `case_mr_health:main`.

## Comandos

Tarefas definidas em `[tool.poe.tasks]` e executadas via poethepoet:

```bash
uv sync                     # instala dependências (incluindo grupo dev)
uv run poe lint             # ruff check
uv run poe format           # ruff check --fix + ruff format
uv run poe test             # lint + pytest com cobertura + relatório HTML
uv run pytest tests/caminho/test_x.py::test_nome   # um único teste
uv run case-mr-health       # roda a CLI
```

## Convenções do projeto

Respeite sempre as convenções já estabelecidas no projeto; ao adicionar código, siga o estilo do código ao redor.

- Ruff: `line-length = 79`, aspas **simples** (`quote-style = 'single'`), regras `I, F, E, W, PL, PT, FAST` com `preview = true`. Rode `uv run poe format` e `uv run poe lint` antes de concluir uma alteração.
- Testes com pytest (`pythonpath = "."`); use estilo pytest (regras `PT`) e fixtures, e `faker` para gerar dados sintéticos.
- Configuração via `pydantic-settings`, logs via `loguru` (não use `print`/`logging`), CLI via `cyclopts`.
- Projeto e textos de changelog em português.
- Commits sem coautoria do Claude
- **Registro para o documento geral do projeto (todas as fases).** O usuário vai escrever (ou pedir) um documento geral com decisões, metodologia, resultados e limitações; portanto cada fase e cada ticket deixam registro suficiente para um agente ou pessoa **sem o contexto da conversa** reconstruir o que foi feito e por quê. Mantenha atualizado a cada ticket:
  - `docs/relatorio/registro-fase<N>.md` (um por fase; parta de `docs/relatorio/_modelo-registro.md`, com `registro-fase1.md` como exemplo): linha do tempo por ticket (o que foi entregue, arquivos, commits, testes), fatos verificados com números e onde conferir, decisões (quem decidiu, quando, justificativa, alternativas), perguntas do usuário com as respostas dadas, hipóteses separadas de evidência, limitações, referências (com localizador; diga o que não foi consultado), pendências e passos de reprodução;
  - **ADRs** em `docs/adr/` para decisões de arquitetura ou de metodologia relevantes, e sinalização explícita quando um resultado contradisser um ADR ou a spec (sem sobrescrever o original em silêncio);
  - seção `## Answer` em cada issue resolvida, com a decisão, os números e as limitações;
  - notebooks com Observação e Interpretação aprovadas, e fragmentos de changelog;
  - decisões formais da política de dados em `.ds-workflow/` quando a skill de ciência de dados estiver em uso.

  Registre também desvios do plano, achados inesperados e o que foi descartado e por quê. Não registre hipótese como fato nem conclusão não aprovada como decidida.

## Issues locais

As issues são rastreadas localmente no repositório, em `issues/<ID>.md` (ID numérico sequencial; o arquivo começa com `# <título>`). O `issue_format` do towncrier gera links para esses arquivos no `CHANGELOG.md`.

- Ao escrever specs/planos, **quebre o trabalho em issues** em `issues/`, cada uma pequena o suficiente para ser uma entrega rastreável no changelog. Use o próximo ID livre.
- Trabalhe cada issue em sua própria branch. Se ainda não existir branch para a issue, crie-a no padrão `<ID_ISSUE>-<titulo_breve>` (ex.: `12-pipeline_features`).

## Changelog (towncrier) — obrigatório

**Toda alteração deve incluir um fragmento de changelog** com towncrier. Fragmentos ficam em `changelogs/` com nome `<ID_ISSUE>.<tipo>.md` (use `+<nome>.<tipo>.md` apenas para mudanças sem issue) e são compilados em `CHANGELOG.md`.

Tipos válidos: `adicionado`, `correcoes`, `alterado`, `removido`, `atualizacoes`, `interno`.

```bash
uv run towncrier create -c "Descrição da mudança." 12.correcoes.md        # vinculado à issue #12
uv run towncrier create -c "Descrição da mudança." +nome-curto.interno.md # sem issue
uv run towncrier build --draft                                            # pré-visualizar o CHANGELOG
```

### Versões

As versões seguem **Semantic Versioning** (`MAJOR.MINOR.PATCH`). Ao concluir um marco/entregável do projeto, **sugira** ao usuário fazer o build do changelog para uma nova versão, propondo o número com base nos fragmentos pendentes (quebra de compatibilidade → MAJOR; `adicionado` → MINOR; apenas correções/internos → PATCH). Após aprovação:

```bash
uv version <nova_versao>                          # atualiza pyproject.toml
uv run towncrier build --yes --version <nova_versao>
```

## Agent skills

### Issue tracker

Issues locais em markdown, em `issues/<ID>.md` (ID numérico sequencial). See `docs/agents/issue-tracker.md`.

### Triage labels

Os cinco papéis canônicos com os nomes padrão, registrados na linha `Status:` de cada issue. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` na raiz. See `docs/agents/domain.md`.
