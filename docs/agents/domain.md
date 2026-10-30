# Docs de domínio

Como as skills de engenharia devem consumir a documentação de domínio deste repositório ao explorar o código.

## Antes de explorar, leia

- **`GLOSSARY.md`** na raiz do repositório.
- **`docs/adr/`**: leia os ADRs que tocam a área em que você vai trabalhar.

Se algum desses arquivos não existir, **siga em silêncio**. Não aponte a ausência nem sugira criá-los de antemão. A skill `/domain-modeling` (acessada via `/grill-with-docs` e `/improve-codebase-architecture`) os cria sob demanda, quando termos ou decisões forem de fato resolvidos.

## Estrutura de arquivos

Repositório de contexto único:

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-exemplo-de-decisao.md
│   └── 0002-outra-decisao.md
└── src/
```

## Use o vocabulário do glossário

Quando sua saída nomear um conceito de domínio (título de issue, proposta de refatoração, hipótese, nome de teste), use o termo como definido em `GLOSSARY.md`. Não troque por sinônimos que o glossário explicitamente evita.

Se o conceito de que você precisa ainda não estiver no glossário, isso é um sinal: ou você está inventando linguagem que o projeto não usa (reconsidere), ou há uma lacuna real (anote para o `/domain-modeling`).

## Sinalize conflitos com ADRs

Se sua saída contradisser um ADR existente, explicite isso em vez de sobrescrever em silêncio:

> _Contradiz o ADR-0007 (…), mas vale reabrir porque…_
