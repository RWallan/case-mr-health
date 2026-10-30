# Encerramento da Fase 1 — apresentação ao usuário

Status das conclusões: **APPROVED (D-005, 2026-10-30)**. A seção 5 (interpretações) segue como hipótese de trabalho. Detalhes e números: `docs/relatorio/registro-fase1.md`.

## 1. O que foi feito (tickets #2 a #6)

| Ticket | Entrega | Testes ao final |
| --- | --- | --- |
| #2 | Base consolidada (pedidos, itens, SKUs) e relatório de qualidade | 17 |
| #3 | Séries diária e semanal por SKU; análise dos 12 dias sem pedido | 21 |
| #4 | Partições de backtest e período OOT selado fisicamente; visão de desenvolvimento | 32 |
| #5 | EDA das séries na visão de desenvolvimento | 45 |
| #6 | Tabela de candidatos por série (módulo `candidatos`, notebook `03_candidatos`, plano congelado) | 90 |

## 2. Testes

`uv run poe test`: **90 testes passaram**, cobertura total de 97%, `candidatos.py` com 100% (evidence: /home/rwallan/git/case-mr-health/.ds-workflow/test-evidence/test-run-20261030T041123-299382.json).  O notebook 03 foi executado de ponta a ponta e passou em `audit_notebook.py` (0 erros, 0 avisos). Os testes novos verificam as regras da tabela (baselines em todas as séries, teto de 4 combinações, exclusões com motivo, base de evidência ou hipótese por SKU); não usam as planilhas reais.

## 3. Observações (o que os números mostram)

- O recálculo na visão de desenvolvimento reproduz a evidência do #5: diárias intermitentes (ADI 1,49 a 1,84; CV² 0,20 a 0,40); semanais suaves (ADI = 1); diárias estacionárias em nível (ADF e KPSS); Ljung–Box não rejeita ruído (p mínimo de 0,14 a 0,39).
- Sazonalidade por dia da semana: confirmada em B (3 de 3 testes com p-Holm < 0,05) e C (2 de 3); inconclusiva em A e D (0 de 3).
- Catálogo: **11 candidatos por série diária** e **5 por série semanal**; nenhum candidato passa de 4 combinações de hiperparâmetros.
- Item C semanal: a semana 07-19 (40 unidades) é o teste do fold 1; nas outras 9 semanas o valor vai de 4 a 19, com mediana 16,0.

## 4. Decisões tomadas por você nesta etapa

1. Branch a partir de `main`; #6 `claimed`.
2. Naive sazonal em A e D como **hipótese**.
3. ARIMA mínimo **entra** na semanal; Prophet **não** entra na semanal.
4. Direção D-003 e plano curto D-004 aprovados; template completo do plano dispensado.

## 5. Interpretações (hipóteses de trabalho, não resultados)

- Entrar na tabela não indica bom desempenho. Os baselines podem vencer em várias séries; isso seria resultado, não falha.
- Croston, SBA e TSB ignoram o dia da semana; nas diárias B e C isso pode limitá-los (hipótese, a verificar no #10).
- Na semanal, SES, Holt amortecido e ARIMA mínimo podem não superar naive e média (H4 e H5 do plano).

## 6. Limitações

- 76 a 79 dias na diária e 10 semanas na semanal; testes do #5 exploratórios, com premissas aproximadas.
- Estacionariedade e autocorrelação semanais não testáveis (n = 10); o ARIMA semanal entra por decisão sua, com base fraca.
- Sazonalidade de A e D inconclusiva por baixo poder; ausência de evidência não é evidência de ausência.
- Com 11 candidatos diários e 4 a 5 folds, há risco de escolha por acaso; o #7 deve comparar com incerteza.
- Venda é proxy de demanda; ruptura aparece como zero.
- Opção A: a diária contém 16/08 a 18/08, dias da semana OOT de 16/08.

## 7. Pontos que pedem sua revisão

1. **SARIMA diário** usa só o sazonal (1,0,0,7); o (0,0,0,7) da direção coincide com o ARIMA sem sazonal.
2. **TSB** com α = β.
3. **ADR 0003:** a exclusão do SARIMA semanal é aritmética (ciclo de 4 ou 52 semanas não cabe em 10 pontos); o ADR não foi alterado.
4. **Correção ao registro (3.5):** a mediana de 16,5 do item C é a das 10 semanas; a das outras 9 é 16,0.
5. Commit `0459a8a` e release 0.2.0 (`5390ff6`) feitos no branch local `6-tabela_candidatos`; sem tag, push nem PR.

## 8. Conclusões

1. APPROVED (D-005): a tabela de candidatos do `candidatos.py` está pronta para guiar o backtest do #7.
2. APPROVED (D-005): pode-se fechar o #6 e a Fase 1 com `Status: resolved`.

## 9. Sugestão de versão

Há fragmentos `adicionado` pendentes (#2 a #6), então sugiro **0.2.0** (MINOR), sem quebra de compatibilidade:

```
uv version 0.2.0
uv run towncrier build --yes --version 0.2.0
```

Executado em 2026-10-30 (`5390ff6`).
