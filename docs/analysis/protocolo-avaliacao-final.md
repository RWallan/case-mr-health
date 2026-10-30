# Protocolo de avaliação final no OOT (#13)

Status: congelado como proposta para aprovação humana.  
Objetivo: avaliar uma única vez os oito modelos selecionados no #12, sem nova
seleção, retreino ou ajuste após observar o OOT.

## População, unidade e horizonte

- Séries: os quatro SKUs (`item A` a `item D`) em granularidade diária e
  semanal, conforme o alias `selecionado` criado pelo #12.
- Unidade: observação de venda por SKU e período.
- Horizonte fixo: os 14 períodos diários e as 2 semanas que compõem o OOT
  separado pelo ADR 0002.
- Antes da primeira leitura do OOT, resolver os oito aliases, conferir que
  cada versão pertence ao SKU/granularidade esperado e verificar o hash do
  artefato. Se qualquer conferência falhar, abortar sem abrir o OOT.
- Uma tentativa é consumida imediatamente antes de abrir o OOT. Falha durante
  a avaliação não autoriza repetição nem substituição do modelo.

## Procedimento congelado

1. Carregar a visão de desenvolvimento para obter a escala do MASE e os
   metadados da partição. Não usar a visão de desenvolvimento para retreinar.
2. Após cumprir os gates da política de dados, abrir `oot_db_path` uma única
   vez, em leitura, e extrair os valores observados para as oito séries.
3. Para cada versão selecionada, produzir a previsão do horizonte fixado e
   comparar, período a período, com os valores observados correspondentes.
4. Calcular MAE, MSE, RMSE, WAPE e MASE conforme as definições implementadas
   em `src/case_mr_health/metricas.py` e ADR 0002. O denominador zero de WAPE
   permanece indefinido; MASE usa a escala do naive de um passo calculada
   somente na visão de desenvolvimento.
5. Para cada nível de intervalo (80% e 95%), calcular cobertura como a fração
   de observações OOT contidas entre os limites inclusivos. Se os limites
   estiverem indisponíveis, registrar cobertura como indisponível, sem
   substituir limites nem recalibrar.
6. Registrar métricas no run MLflow da versão selecionada e gerar gráficos com
   histórico de desenvolvimento, previsão, intervalos e OOT observado.
7. Escrever relatório por série com as métricas, cobertura e diferenças
   descritivas frente às médias de backtest do mesmo run. Não aplicar teste de
   hipótese, intervalo de confiança, limiar inferencial de degradação ou
   confiança de modelo. No semanal, dois pontos são apenas um alerta descritivo
   de degradação grosseira, conforme ADR 0002.
8. Manter a publicação separada da avaliação. Nenhum `champion` será atribuído
   até o usuário decidir a publicação de cada série.

## Regra de parada e integridade

- Não iniciar enquanto a fase não for `final_evaluation`, este protocolo não
  estiver congelado e uma decisão `final_evaluation` não estiver aprovada pelo
  usuário.
- D-019 (seleção) e D-020 (remoção da confiança) também precisam estar
  formalmente aprovadas antes da abertura do OOT.
- A tentativa será marcada antes de abrir o arquivo OOT, de modo exclusivo e
  persistente. Se a marca já existir, a execução deve parar sem ler o OOT.
- O comando não aceita sobrescrita, repetição forçada, seleção alternativa ou
  retreino.

## Evidência e limitações

O período OOT foi reservado previamente pelo ADR 0002. O protocolo apenas
fixa o uso das métricas já implementadas e do horizonte definido pela
partição; não declara antecipadamente qual modelo é melhor nem se haverá
degradação. O OOT não foi aberto durante a preparação deste documento.
