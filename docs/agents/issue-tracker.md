# Issue tracker: Markdown local

As issues e specs deste repositório ficam como arquivos markdown em `issues/`.

## Convenções

- Uma issue por arquivo: `issues/<ID>.md`, com `<ID>` numérico sequencial (sem zero à esquerda). Use sempre o próximo ID livre.
- O arquivo começa com `# <título>`, seguido de linhas de metadados:
  - `Status:` papel de triage (ver `triage-labels.md`) ou `claimed`/`resolved`
  - `Type:` opcional: `spec`, `map`, `task`, `research`, `prototype` ou `grilling`
  - `Parent: #<ID>` opcional: issue-pai (spec ou mapa)
  - `Blocked by: #<ID>, #<ID>` opcional
- Uma spec também é uma issue (`Type: spec`). O trabalho é quebrado em issues filhas, uma por arquivo, com `Parent:` apontando para a spec. Nunca um arquivo único com todos os tickets.
- Comentários e histórico de conversa vão ao final do arquivo, sob o título `## Comments`.
- Cada issue é trabalhada em sua própria branch `<ID>-<titulo_breve>` e exige um fragmento towncrier `changelogs/<ID>.<tipo>.md` (ver `CLAUDE.md`). O `issue_format` do towncrier gera links para `issues/<ID>.md`.

## Quando uma skill disser "publicar no issue tracker"

Crie um novo arquivo `issues/<ID>.md` com o próximo ID livre.

## Quando uma skill disser "buscar o ticket relevante"

Leia o arquivo `issues/<ID>.md`. O usuário normalmente informa o caminho ou o número da issue.

## Operações de wayfinding

Usadas pelo `/wayfinder`. O **mapa** é uma issue com um **filho** por ticket.

- **Mapa**: `issues/<ID>.md` com `Type: map` (corpo com Notes / Decisions-so-far / Fog).
- **Ticket filho**: `issues/<ID>.md` com `Parent: #<ID do mapa>`, a pergunta no corpo, `Type:` (`research`/`prototype`/`grilling`/`task`) e `Status:` (`claimed`/`resolved`).
- **Bloqueio**: linha `Blocked by: #<ID>, #<ID>` perto do topo. Um ticket está desbloqueado quando todas as issues listadas estão `resolved`.
- **Fronteira**: filhos do mapa que estão abertos, desbloqueados e não `claimed`; o de menor ID vem primeiro.
- **Claim**: defina `Status: claimed` e salve antes de qualquer trabalho.
- **Resolve**: acrescente a resposta sob `## Answer`, defina `Status: resolved` e acrescente um ponteiro de contexto (resumo + link) em Decisions-so-far no mapa.
