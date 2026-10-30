# Referência automática da previsão

Status: **APROVADO** pelo usuário em 2026-10-30 (planejamento da onda 6, perguntas Q1 e Q2). Não substitui nenhum ADR; preserva o comportamento do ADR 0011 para quem informa a data.

## Decisão

O usuário não precisa informar a data de referência. O formulário principal pede SKU, granularidade e quantidade de períodos a prever. Sem `data_referencia`, a API usa o **fim do treino** do modelo servido (último período que ele conhece). Depois de um reajuste (ADR 0011), isso coincide com o **último período histórico**. A data manual continua aceita, na área "Avançado" do frontend e no contrato da API, com as validações atuais (passo não negativo; passo mais horizonte até 14 dias ou 2 semanas).

- A previsão toda zero é detectada **no frontend** (todos os valores previstos exatamente 0, com lista não vazia; `null` não é zero). A API devolve o que o modelo gerou, sem campo novo.
- Intervalo `null` não é desenhado nem estimado.

## Por que

Fato verificado em 2026-10-30 (`TestClient`, `item A`): o `champion` diário foi treinado até 2021-08-18 e o semanal até 2021-08-15, com base até 2021-09-01 (semana de 2021-08-23). O frontend enviava a última data da base e a API respondia 422 (passo 21 > 14; passo 4 > 2). O modelo só serve passos a partir do fim do treino, então a referência correta é uma propriedade do modelo, não uma escolha do usuário.

## Alternativas consideradas

- **Referência = último ponto da base, sem reajuste:** inservível; excede o limite validado.
- **Manter a data obrigatória:** preserva o erro do fluxo padrão e exige que o usuário conheça o fim do treino.
- **Calcular a referência no frontend:** duplicaria o conhecimento do modelo servido e divergiria após reajustes.

## Consequências

- Antes de entregar o formulário simplificado é preciso rodar `case-mr-health reajustar` na base atual (#40), senão a previsão automática cobre períodos já observados. O reajuste altera `data/mlflow` (versionado, #32) e as versões novas não têm métrica fora da amostra.
- O contrato muda (campo opcional) e o Swagger acompanha (#39). Nenhum algoritmo, hiperparâmetro ou pipeline de treino muda.
