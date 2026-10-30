# Continuação: ticket #7 (treino de uma série com baselines e MLflow)

Texto pronto para colar numa nova sessão do Claude Code, na raiz do repositório, para um agente **sem o contexto da conversa anterior**. O agente deve invocar a skill `evidence-based-data-science-workflow` e usar este texto como argumento.

---

## Prompt para colar

Vamos executar o ticket #7 da Fase 2 do projeto MR. HEALTH (`issues/7.md`; spec em `issues/1.md`): o comando `case-mr-health treinar` para uma série, com backtest de origem móvel, baselines, métricas e registro no MLflow. A Fase 1 (#2 a #6) está fechada.

### 1. Leia antes de tudo (nesta ordem)
1. `CLAUDE.md`, `GLOSSARY.md`, `docs/adr/0001` a `0005`.
2. `docs/relatorio/registro-fase1.md` (fonte principal: números, decisões, perguntas do usuário, limitações) e `docs/relatorio/encerramento-fase1.md`.
3. `issues/7.md` (critérios de aceite) e `issues/8.md` a `issues/13.md` (o desenho deve permitir plugar candidatos sem mudar o fluxo).
4. `docs/analysis/plano-candidatos.md` e `src/case_mr_health/candidatos.py`: a tabela congelada de candidatos e hiperparâmetros por série; `notebooks/03_candidatos.ipynb`.
5. `src/case_mr_health/particoes.py` (`abrir_desenvolvimento`, `carregar_particoes`), `config.py`, `diagnosticos.py`.
6. Política de dados: `python3 ~/.claude/skills/evidence-based-data-science-workflow/scripts/ds_policy.py status` e `decisions`.

### 2. Regras que valem (não renegocie)
- **OOT selado** até o ticket #13. Use só a visão de desenvolvimento. O hook da skill bloqueia comandos e escritas que citam os nomes dos arquivos selados (veja `config.py` e a política de dados); refira-se a eles de forma genérica.
- Candidatos, hiperparâmetros e baselines vêm de `candidatos.py` (congelado no plano D-004). Mudanças são desvio do plano e exigem aprovação do usuário. Teto de 4 combinações por candidato; sem busca automática de ordem.
- Item C semanal: manter a semana 07-19 (40 unidades) e relatar as métricas com todas as semanas de teste, sem essa semana e sem os folds 1 e 2 (decisão 24 do registro).
- Sazonal em A e D é **hipótese**; separe sempre evidência de hipótese e explicite limitações de amostra (76 a 79 dias; 10 semanas).
- Conclusões e decisões vão à aprovação do usuário antes de serem registradas; a aprovação é feita por ele com `! python3 ~/.claude/skills/evidence-based-data-science-workflow/scripts/ds_policy.py approve D-xxx`.
- Engenharia (`CLAUDE.md`): `src/case_mr_health/`, DuckDB, pydantic-settings, loguru (sem `print`), cyclopts, pytest com fixtures e `faker`, ruff (aspas simples, linha de 79), `uv run poe format` e `uv run poe test`, fragmento `changelogs/7.adicionado.md`, `Status: resolved` ao terminar. **Git e commits só quando o usuário pedir, sem coautoria do Claude.** Pergunte antes de criar a branch `7-treino_baselines`.
- Atualize `docs/relatorio/registro-fase2.md` (parta de `docs/relatorio/_modelo-registro.md`), ADRs se houver decisão de arquitetura e a seção `## Answer` do ticket.

### 3. Pendências herdadas
- O #6 e a Fase 1 estão **aprovados** (D-005) e `resolved`. O commit do #6 (`0459a8a`) e a versão 0.2.0 com o `towncrier build` (`5390ff6`) já foram feitos no branch local `6-tabela_candidatos`. Ainda não há tag, push nem PR para `main`; não os faça sem o usuário pedir.
- Pontos sinalizados para revisão: SARIMA diário só com sazonal (1,0,0,7); TSB com α = β; exclusão do SARIMA semanal contra o ADR 0003 (aritmética).
- Retreino do modelo escolhido com todos os dados após a avaliação final não está no ADR 0002 (sugestão para #13/#14).
