# Sem granularidade mensal: 8 modelos em vez de 12

O histórico cobre 2021-06-01 a 2021-09-01, ou seja, apenas 3 meses completos por SKU. Com 3 observações não há como estimar nem validar um modelo mensal, e não é possível separar treino, teste e OOT. Por isso a granularidade mensal foi removida do escopo: o sistema tem 8 modelos, um por SKU nas granularidades diária e semanal. A especificação original pedia 12.

## Opções consideradas

- **Manter os modelos mensais como baselines sinalizados como insuficientes**: preservaria os 12 identificadores, mas exibiria previsões sem nenhuma base de validação.
- **Gerar dados sintéticos**: descartada, porque inventaria histórico.

## Consequências

- A regra de significância das recomendações ("últimos 3 meses vs. próximos 2 meses") precisa ser reformulada em dias ou semanas.
- Dashboard, API, exportações e contratos aceitam apenas `diaria` e `semanal`.
- Se houver mais histórico (pelo menos dois anos), a granularidade mensal pode voltar.
