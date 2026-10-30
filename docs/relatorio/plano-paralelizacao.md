# Plano de paralelização das issues #8 a #26 (proposta)

Status: **PROPOSTA**, aguarda decisão do usuário. Nada foi disparado em paralelo. Base: campos `Blocked by:` de `issues/*.md` em 2026-10-30, com o #7 implementado e ainda sem commit.

## 1. Grafo de dependências

```
#7 ──┬─► #8 ──┐
     ├─► #9 ──┼─► #14 ─┬─► #15 ──► #24 ◄── #22
     ├─► #10 ─┤        ├─► #16 ──┐
     └─► #11 ─┴─► #12 ─┤        ├─► #25 ◄── #17, #22
                   │   ├─► #17 ──┘
                   ▼   ├─► #22 ──► #23 ◄── #20, #21
                  #13  └─► #19 ◄── #18 ──► #20, #21
                   └────────────────────► #26 ◄── #13, #23, #24, #25
```

Mais precisamente: #12 depende de #8, #9, #10 e #11; #14 de #8 e #9; #13 de #12; #19 de #14 e #18; #26 de #13, #23, #24 e #25. O #18 depende só do #6 (já resolvido).

## 2. Ondas

| Onda | Tickets (em paralelo) | Pré-requisito | Observações |
| --- | --- | --- | --- |
| 0 (agora) | #18 (especificação da regra de recomendação) | #6 | É conversa com o usuário (grilling), não código: pode correr enquanto o #7 é revisado. |
| 1 | #8, #9, #10, #11 | #7 integrado | Quatro frentes independentes. |
| 2 | #12, #14, #17 | #8 a #11 (#12); #8 e #9 (#14); #14 (#17, só precisa do esqueleto da API) | #12 e #14 não se tocam. |
| 3 | #13, #15, #16, #19, #22 | #12 (#13); #14 (os demais) | #13 é sequencial por natureza (abre o OOT uma única vez, aprovação do usuário). |
| 4 | #20, #21, #23, #24, #25 | #19 (#20, #21); #20, #21, #22 (#23); #15 e #22 (#24); #16, #17 e #22 (#25) | Backend e frontend em paralelo. |
| 5 | #26 | #13, #23, #24, #25 | Fecha o projeto. |

Possível antecipação, com custo de retrabalho: começar o #22 (Svelte) na onda 1 contra um contrato OpenAPI fixado antes, já que os testes do frontend (Seam 4) usam API mockada. Só vale se o contrato da resposta de predição (`issues/14.md`) for congelado primeiro.

## 3. O que NÃO paraleliza (gargalo real)

A trilha de modelagem #7 → #12 → #13 passa por portões do usuário que não se resolvem com mais agentes: aprovação do critério de seleção do #12 antes de olhar os resultados; a abertura única do OOT no #13; a decisão de publicação por série. A trilha da API e do frontend (#14 a #26) é a que mais ganha com paralelismo. Os pedidos de aprovação de `D-xxx` devem ser agrupados para o usuário aprovar em lote.

## 4. Pontos de conflito e como evitá-los

- `algoritmos.py`: #10 e #11 registram candidatos. Cada um cria o seu módulo (`algoritmos_intermitentes.py`, `algoritmos_statsmodels.py`) e acrescenta uma linha de importação; o conflito esperado é trivial.
- `treino.py` e `backtest.py`: #8 (intervalos) e #9 (confiança) alteram `_treinar_candidato`. Cada um deve concentrar a lógica em módulo próprio (`intervalos.py`, `confianca.py`) e tocar `treino.py` só no ponto de chamada. Merge sequencial: #8, depois #9.
- `docs/relatorio/registro-fase<N>.md`: arquivo único editado por todos. Cada agente escreve o seu bloco em `docs/relatorio/fase<N>/<ID>.md`; quem integra consolida no registro.
- `CHANGELOG`: sem conflito (um fragmento por ticket).
- `pyproject.toml` e `uv.lock` (FastAPI já está; Svelte e Playwright entram nos #22 e #26): dependências novas só no ticket que as usa; `uv.lock` regenerado ao integrar.
- Política de dados: os agentes herdam o hook; o OOT segue selado. Nenhum agente roda `ds_policy.py approve`.

## 5. Mecânica proposta

- Uma branch e um worktree por ticket (`<ID>-<titulo_breve>`, conforme `CLAUDE.md`), a partir de uma base de integração que contenha o #7. Cada agente de ticket entrega: código, testes, fragmento de changelog, `## Answer` no ticket, bloco de registro e `uv run poe test` verde.
- Integração sequencial na ordem do grafo, com `uv run poe test` na base de integração após cada merge.
- Cada agente propõe, e o usuário aprova, as decisões do seu ticket (`ds_policy.py propose`); as aprovações são feitas em lote.
- Commits e merges só quando o usuário pedir, sem coautoria do Claude.

## 6. Ganho esperado (estimativa qualitativa, não medida)

Com 20 tickets abertos e a cadeia mais longa #7 → #8/#9 → #14 → #19 → #20/#21 → #23 → #26 (7 etapas), a execução em ondas reduz de 20 etapas sequenciais para cerca de 6 ondas, limitada pelas aprovações do usuário na trilha de modelagem.
