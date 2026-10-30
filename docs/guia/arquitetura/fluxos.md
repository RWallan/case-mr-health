# Fluxos

## Previsão e recomendação

1. A interface envia os parâmetros ou uma planilha para a API.
2. A API valida SKU, granularidade, data de referência e horizonte.
3. O serviço seleciona a versão registrada correspondente, produz a previsão e registra o histórico.
4. A recomendação é calculada a partir da série semanal e das regras de estoque. A explicação tenta o provedor LLM quando configurado e usa texto determinístico em caso de indisponibilidade.
5. O resultado retorna à interface; quando solicitado, o resumo pode ser exportado em XLSX.

Fontes: `api/rotas/`, `api/servicos/predicao.py`, `api/servicos/recomendacao.py`, `api/mlflow_cliente.py`; issues #19, #20, #23 a #25.

## Atualização dos dados e reajuste

A carga valida o arquivo, atualiza a base e executa o reajuste das séries suportadas, registrando as versões no MLflow. Esse caminho altera dados operacionais e o registro; não é executado por uma simples consulta de previsão. Fonte: `api/servicos/atualizacao.py`, `api/servicos/reajuste.py` e [ADR 0011](../decisoes/adr/0011-atualizacao-de-dados-pela-api-com-reajuste.md).

## Previsão em lote

O serviço lê as linhas do arquivo, valida cada combinação e agrega resultados e erros por item. O template e o resultado XLSX seguem o contrato implementado no serviço de lote. Fonte: `api/servicos/lote.py`; issue #24.

## Alerta por e-mail

A demonstração prepara uma mensagem de alerta e usa transporte mockado. Não há envio real de e-mail nem garantia de entrega externa. Fonte: `api/rotas/`, `api/servicos/email.py`; issue #21.
