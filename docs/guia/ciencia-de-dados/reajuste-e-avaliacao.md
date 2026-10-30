# Reajuste e avaliação final

## Avaliação final no OOT (#13)

Depois da seleção, a versão `selecionado` de cada série foi avaliada **uma única vez** no OOT (`avaliar_final`, `avaliacao_final.py:372`), segundo o protocolo `docs/analysis/protocolo-avaliacao-final.md` (não lido para esta página). Três travas estão no código:

- os portões da política de dados são conferidos **antes** de abrir o OOT (`verificar_gates`, `avaliacao_final.py:105`);
- se o arquivo de tentativa existir, o OOT não é aberto de novo (`avaliacao_final.py:380-385`: "A avaliação final já foi iniciada"); a marca é gravada imediatamente antes da abertura (`registrar_tentativa`, `:129`), e falha depois dela não autoriza repetição;
- o hash do artefato é conferido ao carregar o modelo (`mlflow_cliente.carregar_conferido`, usado em `avaliacao_final.py:187`).

A avaliação é **descritiva**: compara o OOT com a média do backtest do mesmo run, sem teste de hipótese, sem intervalo de confiança e sem confiança de modelo (D-020) (`13-avaliacao-final.md`, parágrafo de abertura).

### Resultado, citado

Fonte: `docs/relatorio/fase4/13-avaliacao-final.md`. Valores copiados (OOT / backtest), não recalculados.

| Série | Algoritmo (versão) | Períodos | MAE | RMSE | WAPE | MASE | Cobertura 80% | Cobertura 95% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| item A diária | `naive_sazonal` (6) | 14 | 2,500 / 2,143 | 3,284 / 2,791 | 1,129 / 0,897 | 1,010 / 0,811 | 1,000 / 1,000 | 1,000 / 1,000 |
| item B diária | `tsb` (17) | 14 | 1,716 / 2,369 | 1,914 / 2,929 | 1,413 / 1,592 | 0,607 / 0,821 | 1,000 / 0,893 | 1,000 / 0,929 |
| item C diária | `media_historica` (5) | 14 | 1,814 / 2,813 | 1,958 / 3,125 | 0,747 / 1,111 | 0,667 / 1,005 | 1,000 / 0,829 | 1,000 / 1,000 |
| item D diária | `sarima` (9) | 14 | 2,041 / 2,033 | 2,490 / 2,466 | 0,649 / 0,730 | 0,657 / 0,682 | 0,857 / 0,929 | 0,929 / 0,929 |
| item A semanal | `media_historica` (4) | 2 | 3,500 / 3,933 | 3,614 / 3,933 | 0,226 / 0,267 | 0,516 / 0,664 | 1,000 / 0,750 | 1,000 / 1,000 |
| item B semanal | `media_historica` (4) | 2 | 5,500 / 6,750 | 7,433 / 6,750 | 0,440 / 0,687 | 0,500 / 0,605 | 1,000 / 1,000 | 1,000 / 1,000 |
| item C semanal | `media_historica` (4) | 2 | 6,500 / 9,236 | 6,862 / 9,236 | 0,448 / 0,430 | 0,750 / 1,877 | 0,500 / 0,500 | 1,000 / 0,750 |
| item D semanal | `media_historica` (4) | 2 | 1,500 / 4,699 | 1,655 / 4,699 | 0,077 / 0,205 | 0,300 / 0,963 | 1,000 / 0,750 | 1,000 / 1,000 |

**O que o relatório afirma** (`13-avaliacao-final.md`, seção Limitações): séries semanais têm 2 pontos no OOT e servem para notar degradação grosseira, não como evidência estatística; as diárias têm 14 pontos autocorrelacionados, e a cobertura observada tem granularidade de 1/14.

**Leitura permitida e leitura proibida.**

- Permitida (evidência descritiva): item A diária piora no OOT em relação ao backtest em MAE (2,500 contra 2,143) e seu MASE do OOT fica acima de 1 (1,010); item D diária tem MAE do OOT ligeiramente acima (2,041 contra 2,033); nas outras seis séries o MAE do OOT é menor que o do backtest. O MASE do OOT e o do backtest usam escalas diferentes, então a comparação entre eles é só indicativa.
- **Hipótese**, não evidência: que o desempenho "melhor no OOT" em quase todas as séries indique modelos bons. Com 14 e 2 pontos, a diferença pode ser só uma janela mais fácil, e o relatório não testa isso.
- Não permitida: tratar a cobertura de 1,000 como calibração dos intervalos. Ela vem de 14 pontos (diária) ou 2 (semanal), e, nas diárias, o piso zero deixa o intervalo praticamente só com limite superior (ADR 0007).

!!! note "Quando o relatório foi escrito"
    O relatório diz "Nenhum `champion` foi atribuído: a publicação por série é decisão do usuário (`case-mr-health promover`)". Isso descreve o momento da avaliação; hoje há `champion` nas 8 séries (ver abaixo), e ele aponta para uma versão **reajustada**, não para a que foi avaliada.

## Reajuste com dados novos (ADR 0011)

Quando chegam pedidos novos, a API (`POST /dados/pedidos`) ingere os dados e dispara o **reajuste**: o mesmo algoritmo, os mesmos hiperparâmetros e a mesma seed da versão servida são reajustados na série estendida, com novos intervalos calibrados pelo mesmo procedimento do treino (`reajustar_serie`, `reajuste.py:124`). **Não há nova seleção, backtest nem OOT**, e o antigo OOT passa a ser histórico (ADR 0011; `carregar_serie_completa`, `reajuste.py:78`: "Série inteira da base consolidada, incluindo o antigo OOT").

Consequências assumidas no ADR 0011 e confirmadas no código:

- A versão nova é registrada com as tags `origem = atualizacao`, `versao_anterior` e `hash_dados` (`_registrar` em `reajuste.py`) e, se a série serve o `champion` (não fixada por configuração), o alias passa para ela automaticamente (`promovida = fixada is None`).
- **Versões reajustadas não têm métrica fora da amostra.** Backtest e OOT descrevem a versão original.
- Uma falha em uma série não derruba as outras nem troca a versão servida dela (ADR 0011).

### O reajuste #40 de 2026-10-30

Fonte: `issues/40.md` (`## Answer`) e `docs/relatorio/onda6/40.md`. Executado em 2026-10-30, com aprovação do usuário, nas 8 séries, sem falhas:

| Série | Versão anterior | Versão atual (`champion`) | Referência sem data (antes → depois) |
| --- | --- | --- | --- |
| item A, B, C, D diárias | 6, 17, 5, 9 | 19 (nas quatro) | 2021-08-18 → 2021-09-01 |
| item A, B, C, D semanais | 4 (nas quatro) | 6 (nas quatro) | 2021-08-09 → 2021-08-23 |

Conferência independente no registro MLflow (leitura SQLite, sem escrita): as 8 versões 19 e 6 têm `origem = atualizacao`, o `versao_anterior` listado acima e a tag `hash_dados = base`. A issue #40 já registra que `hash_dados = base` **não identifica a base** (valor devolvido por `hash_dados_atual`; não investigado). Logo, o campo "hash dos dados" do ADR 0011 não distingue a base ainda; é limitação conhecida.

!!! warning "Hipótese e limite"
    Nada nos relatórios lidos mostra que o reajuste preserva o desempenho do backtest. O OOT antigo entrou no ajuste, então ele não pode mais medir essas versões; a única evidência cega continua sendo a da seção anterior, sobre versões que já não são as servidas.

## Reavaliação de demonstração (ADR 0012)

O ADR 0012 (aprovado em 2026-10-30) permite que uma pessoa refaça o fluxo com `avaliar-final --demonstracao` e `promover --demonstracao --justificativa`, gravando relatório e marcador em caminhos separados e **sem tocar** no estado do `.ds-workflow/`. A reavaliação **não é cega**: o OOT já foi aberto, então ela não estima desempenho independente e todo o seu material leva o aviso e a tag `modo=demonstracao`. As métricas da seção anterior continuam sendo a única evidência cega.

!!! warning "Estado de implementação"
    O ADR 0012 diz que a implementação está na issue #37; essa issue (e a #35, `retreinar`) está com `Status: ready-for-agent` em `issues/37.md` e `issues/35.md`, e não há ocorrência de "demonstra" em `src/` nem em `tests/` no commit desta documentação. **Portanto a flag `--demonstracao` ainda não existe no código**; a descrição acima é a decisão, não um comportamento verificável. A função `promover` atual (`avaliacao_final.py:419`) exige uma decisão aprovada (`decisoes_aprovadas`) e a tag `oot_avaliado = true` na versão.

## A premissa "um modelo por SKU e granularidade"

A documentação e o glossário afirmam que cada combinação de SKU e granularidade tem o seu modelo (`GLOSSARY.md`, verbete "Modelo"). Verificado no código e no registro, em leitura:

| Aspecto | Evidência | Situação |
| --- | --- | --- |
| Nome | `nome_modelo` (`treino.py:117`) gera `demanda-<sku>-<granularidade>` com SKU em minúsculas e sem espaço; o registro MLflow tem exatamente 8 modelos: `demanda-item-{a,b,c,d}-{diaria,semanal}` | Confirmado |
| Experimento | um por granularidade (`nome_experimento`, `treino.py:123`: `demanda-diaria` e `demanda-semanal`) | Confirmado no código; os nomes dos experimentos não foram listados no banco |
| Alias `champion` | `ALIAS_CHAMPION = 'champion'` (`api/mlflow_cliente.py:24`); o banco tem `champion` em 8 de 8 modelos: versão 19 nas quatro diárias e 6 nas quatro semanais | Confirmado |
| Alias `selecionado` | `selecao.py:26`; 8 de 8: diárias nas versões 6, 17, 5, 9 (A a D) e semanais na 4 | Confirmado |
| Hash do artefato | `hash_artefato` (`treino.py:192`) é o SHA-256 de caminho relativo e conteúdo de cada arquivo; todas as 100 versões têm a tag `hash_artefato` | Confirmado |
| Conferência do hash no carregamento | `carregar_conferido` (`api/mlflow_cliente.py:61`): sem tag, `ModeloRecusado`; hash diferente, `ModeloRecusado("hash divergente ...")`; a conferência é feita na cópia que será carregada | Confirmado no código; testes em `tests/test_api_predicao.py:440` e `:457` |
| Recusa de série errada | `_conferir_serie` (`api/modelos.py:159`) compara as tags `sku` e `granularidade` do **run** com a série pedida; se diferirem, `ModeloRecusado` e a série fica indisponível; teste `test_versao_de_outra_granularidade_e_recusada` (`tests/test_api_predicao.py:354`) | Confirmado |
| Sem fallback | `CatalogoModelos.obter` (`api/modelos.py:61`): "Só a série pedida: nunca a outra granularidade do mesmo SKU"; sem modelo, `ModeloIndisponivel` e "A API não usa outro modelo nem treina um novo" | Confirmado |
| Versão fixada não recai no `champion` | `resolver_versao` (`api/mlflow_cliente.py:42`); teste `test_versao_fixada_inexistente_nao_recai_no_champion` (`tests/test_api_predicao.py:386`) | Confirmado |
| Contrato antes de servir | `_conferir_contrato` (`api/modelos.py:168`): a versão precisa devolver os limites de 80% e 95% até o horizonte máximo | Confirmado |

Ressalvas do que se confirmou:

- **A premissa é um modelo servido por série, não um modelo registrado por série.** O registro guarda **várias versões** por modelo (100 versões em 8 modelos, no banco lido; por exemplo, 19 em `demanda-item-a-diaria`), uma por combinação de candidato e hiperparâmetros treinada, mais as versões reajustadas (ADR 0006). Só uma versão por série responde, a do `champion` ou a fixada por configuração.
- **A recusa de série errada depende de tags do run**, não do nome do modelo. Uma versão registrada no nome certo mas com `granularidade` errada na tag é recusada (teste acima). Um run sem as duas tags faria `obtida` ser `(None, None)` e também seria recusado; isto é leitura do código, sem teste lido.
- **O hash protege contra troca do artefato, não contra escolha errada de versão.** Ele garante que o que se carrega é o que se registrou. Não prova que a versão servida seja a melhor.
- **O hash muda com as dependências**: o MLflow copia `uv.lock` e `pyproject.toml` para o artefato (ADR 0006), e o hash do artefato lido pela API usa a `source` da versão, por causa do arquivo `registered_model_meta` reescrito a cada download (docstring de `api/mlflow_cliente.py:1`).
- **Não executei** treino, reajuste nem chamada à API: a verificação foi por leitura do código, dos testes e do banco SQLite do MLflow em modo somente leitura.

## Limitações desta etapa, juntas

1. **Histórico de cerca de 3 meses** (2021-06-01 a 2021-09-01): 12 semanas por SKU e ~90 dias; semanais com 2 pontos de OOT.
2. **Venda como proxy da demanda**: sem dado de estoque; os zeros imputados são suposição (hipótese).
3. **Versões servidas reajustadas e sem métrica fora da amostra** (reajuste #40 de 2026-10-30, versões 19 diárias e 6 semanais); a única avaliação cega vale para as versões originais.
4. **A avaliação cega foi consumida**; o OOT virou histórico no reajuste (ADR 0011) e a reavaliação de demonstração, quando existir, não será cega (ADR 0012).
5. **`hash_dados = base`** não identifica a base que gerou a versão reajustada (`issues/40.md`).
6. **ARIMA e Prophet fora da tabela** por corte do usuário sem ADR correspondente (ver [Candidatos](candidatos-e-backtest.md)).

## Fontes e limites desta página

Lidos: `avaliacao_final.py` (trechos), `reajuste.py`, `api/modelos.py`, `api/mlflow_cliente.py`, `treino.py` (trechos), `tests/test_api_predicao.py` (títulos e dois testes), `issues/35.md`, `issues/37.md`, `issues/40.md`, `docs/relatorio/onda6/40.md`, `docs/relatorio/fase4/13-avaliacao-final.md`, ADRs 0002, 0006, 0011 e 0012, e o banco `data/mlflow/mlflow.db` (SELECTs em modo `ro`). Não consultados: `.ds-workflow/` (portões e decisões D-019 a D-021), o protocolo de avaliação final, os arquivos de artefato do MLflow, e os experimentos pelo nome.
