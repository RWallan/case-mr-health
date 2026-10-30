# case-mr-health

Modelo preditivo da demanda dos SKUs `item A` a `item D` da MR. HEALTH, em
granularidade diária e semanal, no nível da rede (as unidades não são
identificáveis). O sistema reúne uma API (FastAPI), o rastreio e o registro
dos modelos no MLflow, o histórico de previsões em DuckDB e um dashboard em
Svelte.

!!! warning "Demonstração"
    A previsão é apoio à decisão, não uma ordem de compra. O repositório é uma
    demonstração: não há Docker nem procedimento de deploy (veja
    [Operação](operacao/index.md)).

## Por onde começar

| Se você quer... | Leia |
| --- | --- |
| Entender o problema, os limites e o vocabulário | [Negócio](negocio/index.md) |
| Ver os componentes e como os dados circulam | [Arquitetura](arquitetura/index.md) |
| Saber o que cada funcionalidade faz | [Funcional](funcional/index.md) |
| Entender como o modelo é construído e validado | [Ciência de dados](ciencia-de-dados/index.md) |
| Instalar, executar, testar e manter | [Operação](operacao/index.md) |
| Conhecer as decisões de arquitetura e metodologia | [Decisões](decisoes/index.md) |
| Ver o que diverge entre o planejado e o implementado | [Rastreabilidade](rastreabilidade.md) |

## Como esta documentação foi escrita

Cada afirmação aponta para uma fonte (código, ADR ou relatório). O que não foi
verificado vem marcado como **hipótese** ou **não verificado**. Os contratos
HTTP não são repetidos aqui: o Swagger da API, em `/docs`, é a referência.

Para abrir o site localmente, rode `uv run poe docs`.
