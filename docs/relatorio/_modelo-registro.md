# Registro da Fase <N> — decisões, evidências e questionamentos

> Copie este modelo para `docs/relatorio/registro-fase<N>.md` ao iniciar a fase e preencha a cada ticket. Apague as instruções em itálico depois de preencher cada seção. Referência de nível de detalhe esperado: `registro-fase1.md`.
>
> **Para quem for escrever o documento geral do projeto:** este arquivo deve permitir reconstruir o que foi feito e por quê **sem o contexto da conversa**. Ele separa **fato verificado** (com números e onde conferir), **decisão** (quem decidiu e por quê), **hipótese/interpretação** (ainda não confirmada) e **pendência**. Não apresente hipótese como fato nem conclusão não aprovada como decidida.
>
> Idioma: português. Datas: `AAAA-MM-DD`.

## 1. Escopo da fase

_Objetivo da fase, tickets que a compõem (`issues/<ID>.md`), ADRs e trechos da spec (`issues/1.md`) relevantes, e o que fica fora de escopo._

## 2. Protocolo e regras vigentes

_Regras metodológicas e de engenharia que valem nesta fase (por exemplo, OOT selado, uso apenas da visão de desenvolvimento, convenções do `CLAUDE.md`). Indique o que é herdado de fases anteriores e o que é novo. Se a skill de ciência de dados estiver em uso, cite a fase atual e as decisões formais em `.ds-workflow/`._

## 3. Linha do tempo por ticket

| Ticket | Branch | Commit(s) | Status | Testes ao final |
| --- | --- | --- | --- | --- |
| #<ID> <título> | `<ID>-<titulo_breve>` | `<hash>` | `claimed` / `resolved` | <n> |

### 3.x Ticket #<ID> — <título>

_Repita este bloco por ticket._

**Entregue:** _módulos, comandos, tabelas, notebooks, testes e fragmentos de changelog, com caminhos._

**Regras e decisões de implementação:** _o que foi decidido e por quê, incluindo alternativas descartadas e desvios do ticket._

**Fatos verificados:** _números com a fonte (célula do notebook, consulta, arquivo), tamanho da amostra e período._

**Interpretações (hipóteses):** _marque quem aprovou e quando; indique alternativas consideradas._

**Sinalizações contra ADRs ou a spec:** _divergências encontradas, sem sobrescrever o original; indique se o ADR foi corrigido._

## 4. Decisões consolidadas

| # | Decisão | Quem | Quando | Justificativa | Onde está registrado |
| --- | --- | --- | --- | --- | --- |
| 1 | | Usuário / Agente | AAAA-MM-DD | | ADR, issue, notebook ou decisão `D-xxx` |

_Uma decisão tomada pelo agente sem objeção explícita do usuário deve constar como tal. Decisões revistas mantêm a versão anterior descrita._

## 5. Questionamentos do usuário e respostas dadas (Q&A)

_Para cada pergunta: texto (ou resumo fiel), resposta dada, evidência usada, status (respondida, decidida, em aberto)._

1. **"<pergunta>"** Resposta: … Status: …

## 6. Resultados e conclusões

_Resultados com números, em tabelas. Separe **observação**, **interpretação**, **conclusão aprovada** e **conclusão proposta (não aprovada)**. Cite testes estatísticos com hipótese, premissas, resultado e referência._

## 7. Limitações e riscos

_Amostra, dados, premissas violadas, vazamentos aceitos, suposições de trabalho não confirmadas._

## 8. Referências

- **Consultadas e verificadas** (autor, ano, obra, localizador/página e onde foi consultada).
- **Consultadas sem página** (indique a fonte, por exemplo URL).
- **Citadas sem consulta do texto pelo agente** (não atribuir página a elas).

## 9. Pendências e perguntas em aberto

_Decisões ainda não tomadas, perguntas externas, tarefas que passam para a próxima fase._

## 10. Reprodução e verificação

_Comandos para reproduzir (`uv sync`, comandos da CLI, notebooks), versões relevantes, evidências de testes (`.ds-workflow/test-evidence/...`), avisos de auditoria e como conferir cada resultado._

## 11. Roteiro sugerido para o documento geral

_Contribuição desta fase para o documento geral do projeto: seções que ela alimenta, figuras e tabelas a reutilizar e cuidados de redação (por exemplo, não afirmar ruptura sem dados de estoque)._
