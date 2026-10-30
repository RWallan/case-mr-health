# Regras por funcionalidade

| Regra | Comportamento documentado | Evidência |
| --- | --- | --- |
| Identificação | SKU e granularidade são validados contra as séries/modelos disponíveis. | `api/schemas/`, `api/servicos/predicao.py`; testes `tests/test_api_predicao.py`. |
| Referência | Quando omitida, a API deriva a data de referência conforme os dados disponíveis; quando fornecida, valida o formato e o intervalo. | `api/servicos/predicao.py`; ADR 0013; testes de previsão. |
| Horizonte | A API valida horizonte positivo e limites definidos pelo esquema/serviço antes de prever. | `api/schemas/predicao.py`, `api/servicos/predicao.py`; testes de previsão. |
| Comparação | A comparação entre SKUs é apresentada no dashboard e no XLSX, respeitando o escopo escolhido. | `frontend/src/`, `api/servicos/`; issue #25. |
| Lote | A planilha é validada por linha; resultados válidos e problemas são devolvidos no formato previsto pelo serviço. | `api/servicos/lote.py`; testes `tests/test_api_lote.py`. |
| Exportação | O XLSX inclui resultado e metadados do escopo, e links úteis para a API e changelog. | `api/servicos/`, testes de exportação; issue #25. |
| Recomendação | A regra determinística usa série semanal e parâmetros de cobertura; a explicação por LLM é opcional e tem fallback. | `api/servicos/recomendacao.py`, `api/servicos/explicacao.py`; ADR 0004; issues #19–20. |
| Alerta | O endpoint de demonstração gera e registra uma mensagem usando adaptador mockado. | `api/servicos/email.py`; issue #21. Não envia e-mail externo. |
| Atualização | A operação de carga valida dados e pode iniciar reajuste/versionamento explícito. | `api/servicos/atualizacao.py`, `api/servicos/reajuste.py`; ADR 0011. |

Consulte os módulos e testes citados para os limites numéricos vigentes; os contratos de entrada e resposta são publicados em `/docs` e não são duplicados aqui. O aviso de previsão zero e o tratamento visual de acessibilidade são implementados no frontend (issue #38 e #45).
