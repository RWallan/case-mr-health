# Confiança como metadado da versão, derivada do MASE do backtest, com Insuficiente para MASE indefinido ou instável

Status: **substituído em 2026-10-30** pela decisão D-020, após validação no #12. O texto abaixo preserva a regra histórica implementada pelo #9; ela não integra mais a solução final.

A confiança de cada versão do modelo é calculada só com os folds do backtest (o OOT não entra) e gravada como tags da versão e do run. É metadado para o gestor: não entra em nenhuma seleção. As faixas de MASE ficam em `Settings.confianca_limites`, com limite superior inclusivo: até 0,50 é Ótima; até 0,75, Boa; até 1,00, Média; acima, Ruim. A faixa usa a média simples dos folds, sem arredondar.

O status é **Insuficiente**, que não é Ruim, em três casos, registrados em `confianca_motivo`:

- `mase_indefinido`: o MASE é indefinido em ao menos um fold (escala zero). A média fica indefinida (ADR 0006), e a execução mantém a tag `metricas_indefinidas`. Não se calcula a média só dos folds definidos, para não trocar a amostra em silêncio. Métrica indefinida que não seja o MASE, como o WAPE de um fold sem venda, não afeta a confiança;
- `folds_insuficientes`: menos de 2 folds;
- `mase_instavel`: o IC t de 80% da média dos MASE por fold atravessa duas ou mais fronteiras de faixa. Nível e tolerância são configuráveis (`confianca_nivel_ic`, `confianca_max_fronteiras_ic`).

A faixa que a média indicaria continua gravada em `confianca_faixa_pontual` quando o motivo é instabilidade: é evidência de auditoria, não a confiança do modelo. O critério foi fixado antes de calcular os MASE por fold (`docs/relatorio/fase2/9-pre-registro.md`), e a cobertura do IC é nominal, porque os folds compartilham treino e as séries são autocorrelacionadas.

## Opções consideradas

- **Rótulo pontual com um alerta ao lado**: mantém um rótulo que os dados não sustentam, contra o pedido de não forçar a classificação (#47 da spec).
- **IC de 95%**: com 4 folds, o semi-intervalo é 1,59 dp; ele reflete o tamanho da amostra mais do que o modelo.
- **Jackknife como critério**: não depende de normalidade nem de independência, mas mede só a influência de um fold, não a incerteza da média. Ficou como sensibilidade.
- **Média só dos folds com MASE definido**: contraria o ADR 0006.

## Consequências

- Na validação com baselines (notebook `04_validacao_confianca.ipynb`), 15 de 20 runs ficam Insuficiente, incluindo os 8 semanais, e as faixas não discriminam pelo critério pré-registrado. O usuário decide se mantém a regra; a validação precisa ser repetida depois de integrar #10 e #11.
- A API e o e-mail (#14 a #16) precisam tratar `Insuficiente` e não podem exibir `confianca_faixa_pontual` como se fosse a confiança.
- O #13 revisa a confiança depois do OOT sem apagar a do backtest: deve gravar tags próprias.
- MASE abaixo de 1 não significa ganhar do baseline: a escala é o naive de um passo dentro do treino.
- Esta decisão não muda a escala do MASE. A revisão pedida no ADR 0006 foi feita e não recomenda a troca para lag 7, que segue como decisão do usuário.

## Revisão (2026-10-30, D-020)

A validação repetida no #12 mostrou que a confiança é inútil pelo critério pré-registrado: apenas 2 dos 8 modelos selecionados saíram de Insuficiente; I1 e I3 dispararam; 45 dos 72 runs e todos os 12 semanais ficaram Insuficiente. A alternativa pareada também falhou nos baselines (2 de 12 pares, mínimo de 3). O usuário decidiu remover a confiança da solução final. O módulo, a configuração, as tags, o campo da API e o registro de confiança no histórico foram removidos no #27. O notebook de validação e os registros desta fase permanecem como evidência histórica.
