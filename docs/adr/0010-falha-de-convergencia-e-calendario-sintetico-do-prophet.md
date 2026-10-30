# Falha de convergência invalida a combinação inteira, e o Prophet usa calendário sintético

Status: **PROPOSTA**, aguarda aprovação do usuário (ticket #11).

O contrato `ajustar(y)` (ADR 0006) recebe só um array, e o backtest compara médias de folds (ADR 0002). Os candidatos do `statsmodels` e o Prophet podem não convergir, e o Prophet precisa saber em que ponto do ciclo semanal está.

**Falha.** Um ajuste falha quando a estimação levanta erro numérico, quando o otimizador emite `ConvergenceWarning`, quando informa `converged = False` ou quando devolve parâmetros não finitos. Basta um fold, ou o ajuste final com todo o desenvolvimento, falhar para a **combinação inteira** (candidato × hiperparâmetros) falhar: `treinar_serie` abre um run `FAILED` com as tags `falha_convergencia`, `falha_ajuste` e `falha_motivo`, os parâmetros e `diagnosticos.json`, sem métricas e sem versão de modelo, e segue para a próxima combinação.

**Premissas.** Cada `ajustar` verifica as premissas com o próprio treino. O resultado vai para o artefato `diagnosticos.json` e para as tags `premissas_nao_atendidas` e `premissas_nao_testaveis`. Verificar não reprova: premissa não atendida ou não testável não tira a combinação do treino. O que fazer com elas é decisão do critério do #12.

**Prophet.** A série ganha um calendário sintético de dias consecutivos com início fixo. A sazonalidade é uma soma de Fourier de período 7 com coeficientes livres e priori isotrópica, então mudar o início só gira a fase, e o modelo aprende a fase dos dados. O dia da semana nominal não é usado. A premissa é a série não ter buracos, o que vale porque dia sem venda é zero imputado.

## Opções consideradas

- **Média só dos folds que convergiram**: compara médias sobre folds diferentes, e o candidato escolheria os folds em que é avaliado.
- **Trocar o fold falho por um baseline**: esconde a falha e atribui ao candidato um erro que não é dele.
- **Aceitar a estimativa com aviso e só marcar uma tag**: mantém métricas de um ponto que não é ótimo.
- **Reduzir a combinação a `nan` na média** (como métrica indefinida): perderia a distinção entre métrica indefinida e modelo que não existe.
- **Passar a data de início ao previsor** (argumento de construtor ou método opcional): muda o contrato, ou exige que o fluxo saiba quem precisa de data, sem ganho na previsão.

## Consequências

- Candidato que falha em um único fold sai da comparação do #12. O #12 deve filtrar `attributes.status = 'FINISHED'`.
- Série constante ou perfeitamente periódica pode falhar de verdade, e isso aparece como falha registrada, não como erro do comando.
- O contrato `Previsor` não muda: os diagnósticos saem por um coletor de contexto (`coletar_diagnosticos`), e o rótulo do ajuste (`fold_<i>`, `modelo_final`) é deduzido do tamanho do treino, portanto ajustes extras de outro mecanismo aparecem como `ajuste_n<k>` em vez de deslocar os folds.
- Componentes do Prophet não podem ser lidos como "segunda-feira": só a posição no ciclo tem sentido.
