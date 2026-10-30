# Contexto

MR. HEALTH é uma rede de restaurantes com cerca de 50 unidades. O sistema estima demanda futura para quatro SKUs agregados (item A a item D) e oferece apoio à reposição. A base demonstrativa cobre 93 dias, de 2021-06-01 a 2021-09-01; as unidades não são identificáveis e, portanto, a previsão é da rede, não de cada loja. A especificação do domínio está em `issues/1.md` e o histórico e limitações dos dados em [Dados e partições](../ciencia-de-dados/dados-e-particoes.md).

A previsão é apoio à decisão, não uma ordem de compra. A saída deve ser interpretada junto do histórico, da incerteza e das regras operacionais. Para detalhes da API consulte o Swagger em `/docs`.

**Evidência:** `src/case_mr_health/dados/` e `src/case_mr_health/api/servicos/predicao.py`; [ADR 0004](../decisoes/adr/0004-recomendacoes-pela-serie-semanal.md).
