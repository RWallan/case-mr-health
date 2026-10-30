# Dados e partições

## Da planilha à série

Três planilhas (pedidos, itens de pedido e itens/SKU) são validadas e consolidadas em DuckDB por `preparar_dados` (`dados.py:71`). Linhas inválidas abortam a execução sem escrever nada (docstring de `dados.py:71`). As regras de validação estão na [página funcional](../funcional/regras.md); aqui interessa o que vira série.

`construir_series` (`series.py:1`) cria duas tabelas:

| Conceito | Regra | Fonte |
| --- | --- | --- |
| Calendário do SKU | Da primeira venda do SKU até o último dia com pedido na rede | docstring de `series.py:1`; `GLOSSARY.md` ("Calendário do SKU") |
| Zero imputado | Dia do calendário sem venda recebe `quantidade = 0` e `imputado = true` | `series.py` (`coalesce(v.quantidade, 0)` e `v.quantidade IS NULL AS imputado`) |
| Semana | Segunda a domingo, rotulada pela segunda-feira | docstring de `series.py:1`; `GLOSSARY.md` ("Semana") |
| Período incompleto | Semana sem os 7 dias dentro do calendário do SKU não entra na série semanal | `series.py` (`HAVING count(*) = 7`); `GLOSSARY.md` ("Período incompleto") |

Duas consequências conceituais:

- **Antes da primeira venda não há série.** O SKU não ganha zeros anteriores ao seu primeiro dia de venda. Por isso SKUs com início diferente têm séries de tamanhos diferentes (no registro MLflow, as versões reajustadas de item B e D diárias têm 90 observações, e as de item A e C, 93: parâmetro `n_observacoes`).
- **Zero imputado é uma premissa, não um dado observado.** Ele assume que dia sem pedido significou venda zero. A série diária resultante é intermitente: entre 33% e 46% dos dias de cada SKU não têm venda na visão de desenvolvimento (ADR 0003, citando a EDA do ticket #5). É por isso que os métodos de demanda intermitente entram entre os candidatos.

!!! note "Hipótese, não evidência"
    Que todo zero imputado seja "demanda zero" é uma hipótese de trabalho. Os relatórios lidos não a testam.

## Por que só duas granularidades

O histórico tem 3 meses completos por SKU, o que não permite estimar nem validar um modelo mensal. A granularidade mensal foi removida e o sistema tem **8 modelos**: 4 SKUs por 2 granularidades (ADR 0001, [texto](../decisoes/adr/0001-sem-granularidade-mensal.md)). A alternativa de gerar dados sintéticos foi descartada porque inventaria histórico.

## Partições: desenvolvimento, folds e OOT

`particionar` (`particoes.py:50`) usa **apenas as datas** dos períodos, nunca os valores de venda: o corte não pode depender do que a série fez. Os tamanhos vêm de `Settings` (`config.py`, bloco "Partições") e do ADR 0002 ([texto](../decisoes/adr/0002-backtest-origem-movel-e-oot-selado.md)):

| Parâmetro | Diária | Semanal | Fonte |
| --- | --- | --- | --- |
| OOT (últimos períodos) | 14 dias | 2 semanas | `config.py` (`oot_diaria_dias`, `oot_semanal_semanas`); ADR 0002 |
| Tamanho do fold de teste | 7 dias | 1 semana | `config.py` (`fold_diaria_dias`, `fold_semanal_semanas`) |
| Treino mínimo | 42 dias | 6 semanas | `config.py` (`treino_minimo_diaria_dias`, `treino_minimo_semanal_semanas`) |

O treino é uma janela **expansiva**: todo fold começa no início do desenvolvimento e termina um período-fold depois do anterior (`particoes.py:67-77`). O teste de cada fold é o bloco seguinte ao treino.

```text
desenvolvimento  |-- treino fold 1 --|teste 1|
                 |---- treino fold 2 ----|teste 2|
                 |------ treino fold 3 ------|teste 3| ...   | OOT (selado) |
```

### Separação física do OOT

`separar_series` (`particoes.py:88`) grava dois arquivos DuckDB: a visão de desenvolvimento, sem o OOT, com as tabelas `particao` e `fold` (`particoes.py:139`), e outro só com o OOT (`particoes.py:196`). A EDA, a seleção e o backtest abrem apenas a primeira (`abrir_desenvolvimento`, `particoes.py:224`: "a única visão permitida para a EDA e o treino"). O sigilo do OOT é, portanto, estrutural, e não só uma convenção.

### Por que origem móvel e OOT

As séries são curtas (cerca de 90 dias na diária e 12 semanas completas na semanal). Um único corte de teste daria poucos pontos e métricas instáveis; por isso o "teste" é a média dos folds de um backtest de origem móvel, e um período final fica reservado (ADR 0002). Toda transformação com parâmetros estimados é ajustada dentro de cada fold, só com o treino do fold.

**Limitação registrada no ADR 0002:** o OOT semanal tem 2 pontos e serve para detectar degradação grosseira, não como evidência estatística forte.

### Exceção: reavaliação de demonstração

O ADR 0012 relativiza a regra "o OOT só é usado na validação final": uma pessoa que retreina o projeto pode reabrir o OOT, mas o resultado vem rotulado como reavaliação de demonstração (ver [Reajuste e avaliação final](reajuste-e-avaliacao.md)).

## Fontes e limites desta página

Lidos: `series.py`, `particoes.py`, `config.py`, `dados.py` (só o fluxo de `preparar_dados`), `GLOSSARY.md` e os ADRs 0001, 0002, 0003 e 0012. As datas reais de cada partição ficam no MLflow (`desenvolvimento_inicio` e `desenvolvimento_fim` por versão) e nas tabelas `particao` e `fold` do arquivo de desenvolvimento, que não foi aberto aqui.
