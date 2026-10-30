# Treino por candidato plugável, com uma versão do modelo por execução e sem seleção no treino

O comando `treinar` percorre a tabela de candidatos do #6 (`candidatos.py`) e, para cada candidato com implementação e cada combinação de hiperparâmetros, faz o backtest de origem móvel e registra uma execução (run) no MLflow. Um candidato novo (#10, #11) entra escrevendo uma classe com `ajustar(y)` e `prever(horizonte)` e registrando-a em `algoritmos.ALGORITMOS` com o nome do `algoritmo` da tabela; as chaves do espaço de hiperparâmetros são os argumentos do construtor. O fluxo (`backtest`, `treino`) não muda. Candidatos da tabela sem implementação são reportados no log e no resumo, nunca descartados em silêncio.

Cada execução ajusta o previsor com todo o desenvolvimento e o registra como **uma versão** de `demanda-<sku>-<granularidade>` (SKU em minúsculas e sem espaço, por exemplo `demanda-item-a-diaria`), com os metadados `algoritmo`, `hiperparametros`, `run_id` e `hash_artefato`. O treino não seleciona nem promove nada: a escolha da versão de cada série é do #12 (só pelo backtest) e o alias `champion` é do #13 (ADR 0005).

## Opções consideradas

- **Registrar só o melhor baseline por série**: exigiria um critério de seleção antes de o #12 defini-lo, e o #12 precisa comparar todos os candidatos.
- **Um modelo registrado por algoritmo** (`demanda-<sku>-<granularidade>-<algoritmo>`): contraria a nomenclatura do ADR 0005 e complica o carregamento do `champion` pela API.

## Consequências

- Cada execução do `treinar` acrescenta versões (3 por série diária e 2 por semanal só com baselines; mais com os candidatos do #10 e #11). Não há limpeza de versões antigas; o #12 deve escolher pelo `run_id` e pela seed registrados.
- O hash do artefato é o SHA-256 do diretório do modelo baixado do MLflow. Como o MLflow copia `uv.lock` e `pyproject.toml` para o artefato, o hash muda quando as dependências mudam, mesmo com o mesmo previsor.
- A média dos folds é a média simples das métricas por fold (ADR 0002). Se uma métrica é indefinida em algum fold (WAPE com venda zero; MASE com escala zero), a média é indefinida: a métrica não é registrada e a execução recebe a tag `metricas_indefinidas`. O #9 trata a escala zero como Insuficiente.
- O MASE usa como escala o MAE do naive de um passo no treino de cada fold (Hyndman e Koehler, 2006). Na diária, com sazonalidade semanal, a escala de lag 7 é uma alternativa; a escolha da escala é hipótese e deve ser revista no #9 ao validar as faixas.
