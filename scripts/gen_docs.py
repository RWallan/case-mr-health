"""Hook do MkDocs: injeta ADRs e tokens no build, sem cópia commitada (#47).

Só `docs/adr/*.md` e `design/tokens.css` saem do diretório do guia;
`docs/relatorio/`, `docs/analysis/` e `docs/agents/` não são publicados.
"""

from pathlib import Path

import mkdocs_gen_files

RAIZ = Path(__file__).resolve().parent.parent
ADRS = sorted((RAIZ / 'docs' / 'adr').glob('*.md'))

# Tokens compartilhados com o frontend (fonte única das cores).
tokens = RAIZ / 'design' / 'tokens.css'
with mkdocs_gen_files.open('stylesheets/tokens.css', 'w') as f:
    f.write(tokens.read_text(encoding='utf-8'))

# ADRs: cada arquivo vira página em decisoes/adr/.
for adr in ADRS:
    with mkdocs_gen_files.open(f'decisoes/adr/{adr.name}', 'w') as f:
        f.write(adr.read_text(encoding='utf-8'))

# Índice dos ADRs a partir do título de cada arquivo.
with mkdocs_gen_files.open('decisoes/index.md', 'w') as f:
    f.write('# Decisões (ADRs)\n\n')
    for adr in ADRS:
        titulo = adr.read_text(encoding='utf-8').splitlines()[0]
        titulo = titulo.lstrip('# ').strip() or adr.stem
        f.write(f'- [{titulo}](adr/{adr.name})\n')
