# Previsão de demanda — MR. HEALTH

Previsão da demanda futura de cada SKU da rede MR. HEALTH, a partir do histórico de pedidos, para apoiar decisões de reposição e redução de estoque.

## Vendas observadas

**Pedido**:
Registro de uma compra na rede, com identificador e data.
_Evitar_: transação, venda (para o registro)

**Item de pedido**:
Linha de um pedido que associa um SKU a uma quantidade. O mesmo SKU pode aparecer em mais de um item do mesmo pedido; as quantidades se somam.
_Evitar_: item (isolado), produto

**SKU**:
Produto do cadastro (`item A` a `item D`), com um valor unitário. É a unidade de previsão.
_Evitar_: item, produto

**Valor unitário**:
Preço de um SKU no cadastro. Interpretação inferida: a planilha de cadastro não tem cabeçalho e o case não a define; não confirmada; mantida como suposição de trabalho por decisão do usuário.
_Evitar_: preço médio, valor do item

**Valor do item**:
Quantidade de um item de pedido multiplicada pelo valor unitário do SKU.

**Valor total do pedido**:
Soma dos valores dos itens de um pedido.

**Venda**:
Quantidade de um SKU efetivamente vendida em um período.
_Evitar_: demanda (para o que foi observado)

**Zero imputado**:
Período sem nenhuma venda registrada de um SKU, representado como venda igual a zero.
_Evitar_: valor faltante, dado ausente

## Previsão

**Demanda**:
Quantidade de um SKU que se espera vender em um período futuro, estimada a partir da venda. Não observa rupturas: venda perdida por falta de estoque é invisível.
_Evitar_: venda (para o que foi previsto)

**Rede**:
Nível de agregação de todas as unidades somadas; é o único nível em que a demanda é prevista.
_Evitar_: loja

**Unidade**:
Restaurante da rede. Não é identificável nos dados disponíveis.
_Evitar_: filial, loja

**Granularidade**:
Tamanho do período de uma série: diária ou semanal.
_Evitar_: frequência, horizonte

**Semana**:
Período de segunda-feira a domingo, identificado pela data da segunda-feira.

**Período incompleto**:
Semana que não tem todos os seus dias dentro do calendário de um SKU. Não compõe a série semanal.

**Calendário do SKU**:
Dias entre a primeira venda do SKU e o fim do histórico da rede. Antes da primeira venda não há série; depois dela, todo dia sem venda é um zero imputado.

**Série**:
Sequência de vendas de um SKU em uma granularidade, dentro do calendário do SKU.

**Modelo**:
Estratégia preditiva de uma única série. Cada combinação de SKU e granularidade tem o seu.
_Evitar_: modelo do SKU (sem granularidade)

**Horizonte**:
Quantidade de períodos futuros previstos por um modelo. Limitado ao tamanho do período OOT da granularidade, que é o máximo validado empiricamente.
_Evitar_: granularidade, prazo

**Período OOT**:
Trecho final de uma série reservado para avaliar o modelo depois de escolhido, sem participar do treino nem da seleção.
_Evitar_: validação, holdout

**Confiança**:
Classificação de um modelo (Ótima, Boa, Média ou Ruim) a partir do erro histórico relativo ao seu baseline. Não é garantia de acerto.
_Evitar_: acurácia, certeza

**Insuficiente**:
Situação em que não há evidência para atribuir confiança a um modelo ou para considerar uma variação significativa.
_Evitar_: Ruim (são coisas diferentes)

## Estoque

**Recomendação**:
Orientação de estoque para um SKU, derivada de forma determinística da comparação entre demanda prevista e venda recente: aumento significativo, redução significativa, estável ou Insuficiente.
_Evitar_: alerta (o alerta é a comunicação da recomendação)

**Variação significativa**:
Variação entre a demanda prevista e a venda recente que supera o terceiro quartil das variações históricas de mesmo formato, calculado separadamente para aumentos e reduções.

**Pressão sobre o estoque**:
Sinal de aumento relevante de demanda prevista que pode exigir atenção à reposição.
_Evitar_: ruptura, falta de estoque

**Ruptura**:
Falta de estoque para atender à demanda. Só pode ser afirmada com dados de estoque, pedidos de compra e prazos de reposição.
_Evitar_: pressão sobre o estoque
