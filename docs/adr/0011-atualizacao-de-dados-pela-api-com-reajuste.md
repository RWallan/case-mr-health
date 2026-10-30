# Atualização de dados pela API com reajuste do modelo

Status: **APROVADO** pelo usuário em 2026-10-30, com as duas opções propostas (promoção automática; OOT antigo vira histórico no reajuste). Altera o ADR 0005 no ponto "a API nunca treina".

## Decisão

Quando chegam pedidos novos (as planilhas de pedidos e de itens de pedido, nos mesmos formatos das brutas), o usuário os envia pela API. O envio dispara, no serviço, a ingestão e o **reajuste** dos modelos, para que a previsão e o gráfico da série passem a partir do histórico atualizado. Um modelo ajustado não enxerga pedido novo; sem reajuste, a previsão não muda.

- **Ingestão.** `POST /dados/pedidos` recebe os dois XLSX, valida com as regras de `preparar_dados` (erros com campo e linha) e acrescenta os pedidos novos à base. Um pedido já presente na base é rejeitado, e o mesmo arquivo (SHA-256) enviado duas vezes não é aplicado duas vezes. As séries diária e semanal são reconstruídas.
- **Reajuste.** Para cada série, o **mesmo algoritmo e os mesmos hiperparâmetros** da versão servida (lidos do run de origem) são reajustados na série estendida. Não há nova seleção, backtest nem reabertura do OOT. Os intervalos são recalibrados pelo mesmo procedimento do treino. O resultado é uma **nova versão** no Registry, com hash, tags `origem=atualizacao`, `versao_anterior` e `hash_dados`, e `desenvolvimento_fim` igual ao fim da série nova.
- **Execução.** Em segundo plano, uma atualização por vez (um único worker, ADR 0005). A validação dos arquivos é síncrona (erros 422 com campo e linha, 409 para arquivo já aplicado); só o reajuste é assíncrono. A rota responde 202 com um identificador, e `GET /dados/atualizacoes/{id}` informa estado (`em_andamento`, `concluida`, `concluida_com_erros` ou `falhou`), séries reajustadas e erros. Uma falha numa série não derruba as outras nem troca a versão servida dela.
- **Serviço.** Depois de reajustada, a série passa a servir a versão nova sem reiniciar a API. O alias `champion` é movido para ela **de forma automática** e registrado (versão anterior, nova e hash); voltar à anterior é `case-mr-health promover`. 
- **Janela.** A origem fixa da predição passa a ser o fim da série nova. O horizonte continua limitado a 14 dias ou 2 semanas depois dela.

## Pontos confirmados pelo usuário

1. **Promoção automática.** A alternativa é a versão nova ficar sem `champion` até o usuário promovê-la; a API serviria a versão antiga enquanto isso, e o gráfico não mudaria.
2. **OOT antigo.** Os últimos 14 dias e 2 semanas do OOT passam a ser histórico no reajuste, o que só é válido porque a avaliação final do #13 já foi consumida (D-021). O reajuste não é validado em período algum.

## Consequências

- O ADR 0005 muda: a API passa a treinar, só por este caminho, e nunca em requisição de predição. O histórico de previsões continua o mesmo.
- Versões reajustadas **não têm métrica fora da amostra**: o backtest e o OOT descrevem a versão original. A resposta e o dashboard precisam dizer isso.
- Reajuste de SARIMA e Prophet leva tempo; por isso o processamento é assíncrono e serializado.
- A base e as séries deixam de ser imutáveis. Cada atualização guarda o hash dos dados que a gerou, para reproduzir a versão.
- A ingestão aceita pedidos novos, não correções de pedidos antigos.
