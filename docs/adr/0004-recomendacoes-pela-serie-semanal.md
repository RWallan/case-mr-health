# Recomendações baseadas no modelo semanal (4 semanas vs. 2 semanas)

A regra original ("últimos 3 meses vs. próximos 2 meses") não é aplicável, porque não há granularidade mensal (ADR 0001). As recomendações passam a usar o modelo semanal: comparam a demanda média prevista para as próximas 2 semanas com a venda média das últimas 4 semanas. A variação é significativa quando supera o terceiro quartil das variações históricas de janelas deslizantes com o mesmo formato. Aumentos e reduções têm limites separados.

## Opções consideradas

- **Modelo diário (28 dias vs. 14 dias)**: gera cerca de 50 variações históricas, mas as janelas se sobrepõem fortemente e são autocorrelacionadas. Isso dá uma falsa sensação de precisão ao Q3.

## Consequências

- Com 12 semanas completas, existem apenas cerca de 7 variações históricas. Toda recomendação é apresentada com aviso de baixa confiabilidade estatística, e o resultado é Insuficiente quando não houver variações suficientes.
- A especificação detalhada da regra é feita e aprovada na Fase 6, antes da implementação.
