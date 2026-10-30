# Registro da Onda 6 — interface, gráfico de previsão e documentação (#38 a #51)

Data: 2026-10-30
Escopo: planejamento (sem implementação) de melhorias do frontend, do gráfico de previsão e da documentação em MkDocs Material. Nenhum código, modelo ou pipeline foi alterado. Foram criados só: `docs/adr/0013-referencia-automatica-da-previsao.md`, termos no `GLOSSARY.md`, as issues `38.md` a `51.md`, este registro `docs/relatorio/plano-paralelizacao-onda6.md` e `changelogs/+planejamento-onda6.interno.md`.

## 1. Linha do tempo

| Ticket | Tema | Depende de | Status |
| --- | --- | --- | --- |
| #38 | Gráfico: eixo por data, histórico/previsão, alerta de zero | — | `ready-for-agent` |
| #39 | API: `data_referencia` opcional | — | `ready-for-agent` |
| #40 | Reajustar as 8 séries na base atual | #39 | `ready-for-agent` |
| #41 | Formulário simplificado e "Avançado" | #39, #40 | `ready-for-agent` |
| #42 | Tokens de design e componentes base | — | `ready-for-agent` |
| #43 | Upload reutilizável | #42 | `ready-for-agent` |
| #44 | Seção LLM e segurança da chave | #42 | `ready-for-agent` |
| #45 | Responsividade e acessibilidade | #42, #43 | `ready-for-agent` |
| #46 | Changelog dentro do app | #42 | `ready-for-agent` |
| #47 | MkDocs Material, tokens, poe e link no frontend | #42 | `ready-for-agent` |
| #48 | Docs: arquitetura e regras de negócio | #47, #41 | resolvida |
| #49 | Docs: Ciência de Dados e ML | #47 | `ready-for-agent` |
| #50 | Docs: operação e Swagger | #47 | `ready-for-agent` |
| #51 | Revisão final | #38 a #50 | resolvida |

Ordem adotada: a de referência do pedido, com um ajuste justificado. A correção do gráfico (#38) e a referência automática (#39, #40) vêm antes porque o formulário simplificado só funciona depois do reajuste (D1). Os tokens (#42) antecedem uploads, LLM, acessibilidade, changelog e MkDocs, que os reutilizam.

Plano de paralelização em ondas: `docs/relatorio/plano-paralelizacao-onda6.md` (proposta; aguarda decisão do usuário).

## 2. Diagnóstico (fatos verificados e hipóteses)

Verificado = lido no código ou executado em 2026-10-30. Hipótese = não confirmado.

| ID | Problema | Local | Evidência | Causa | Prioridade |
| --- | --- | --- | --- | --- | --- |
| D1 | Previsão do formulário falha com os modelos atuais | `App.svelte` (`carregarSerie` preenche a referência com o último ponto); `servicos/predicao.py::planejar` | `TestClient`, `item A`: diária ref. 2021-09-01 h=7 → 422 (passo 21); semanal ref. 2021-08-23 h=2 → 422 (passo 4); diária ref. 2021-08-18 h=7 → 200. MLflow: `desenvolvimento_fim` 2021-08-18 (diária) e 2021-08-15 (semanal); base até 2021-09-01. Sem versões `origem=atualizacao` | **Confirmada**: o limite é 14 dias/2 semanas após o fim do treino, e o `champion` nunca foi reajustado | Alta |
| D2 | Previsão desenhada em datas erradas | `App.svelte`: `x(historico.length + indice, …)` | Leitura do código: posição por índice, sem uso de `data_alvo`; com referência anterior ao último ponto, a previsão aparece depois do histórico | **Confirmada** (leitura; não reproduzida em navegador) | Alta |
| D3 | Previsão pouco evidente | `App.svelte` | ~90 pontos de histórico contra 7 de previsão na mesma largura; sem tooltip; início só por linha pontilhada sem rótulo | **Confirmada** (leitura) | Alta |
| D4 | Intervalo fabricado | `App.svelte`: `limite_inferior_95 ?? 0`, `limite_superior_95 ?? quantidade_prevista` | O schema admite `null` (`PeriodoPrevisto`) e o frontend o transforma em faixa | **Confirmada** | Alta |
| D5 | Sem tratamento de previsão toda zero | `App.svelte`, `EntradaPrevisoes.svelte` | Nenhuma ocorrência de regra ou alerta | **Confirmada** (ausência) | Alta |
| D6 | Changelog abre JSON | `LinksApi.svelte` → `GET /changelog`; `rotas/changelog.py` | A rota devolve `Changelog` estruturado, não Markdown; o arquivo real é `CHANGELOG.md` (o pedido cita `CHANGELOGS.md`) | **Confirmada**: não é falha de servidor nem de segurança | Média |
| D7 | Estilo inconsistente | `style.css` | Só `.controls` estiliza `select` e `input`; `EntradaPrevisoes`, `update` e `Recomendacoes` usam o nativo; cores em hexadecimal solto, sem variáveis | **Confirmada** (leitura) | Média |
| D8 | Numeração duplicada | `EntradaPrevisoes.svelte` e `Recomendacoes.svelte` | Ambas com `04`; `ComparacaoSkus` sem `step` | **Confirmada** | Baixa |
| D9 | Upload sem estados | `App.svelte` seção 03, `EntradaPrevisoes.svelte` | `input type=file` nativo, sem arrastar, sem remover; `fetch` não reporta progresso | **Confirmada** | Média |
| D10 | Chave do LLM pode vazar por log ou erro | `explicacao.py`, `rotas/recomendacoes.py` | O frontend mantém a chave só em memória e usa cabeçalho. O código afirma que a chave não vai para o log, mas o comportamento do `litellm` em exceções **não foi verificado** | **Hipótese** (auditar em #44) | Alta |
| D11 | Acessibilidade e responsividade | todo o frontend | `.workspace` com coluna de 285 px; textos de 9 a 11 px; cores como `#9aa69f` sobre branco; `ComparacaoSkus` não foi lida por completo | **Hipótese** quanto ao contraste e aos rótulos (medir em #45) | Média |
| D12 | Docker, Compose e deploy não existem | raiz do repositório | Nenhum Dockerfile ou compose versionado; tarefas poe: `backend`, `mlflow`, `frontend`, `frontend-build`, `app` | **Confirmada** (ausência) | Informativa |
| D13 | MkDocs inexistente | raiz | Nenhum `mkdocs.yml`; `docs/` guarda ADRs, relatórios internos, análises e scripts | **Confirmada** | — |

## 3. Decisões (usuário, 2026-10-30)

| # | Decisão | Onde |
| --- | --- | --- |
| 1 | Referência automática = fim do treino do modelo servido; data manual em "Avançado"; reajuste da base atual como pré-requisito | ADR 0013, #39 a #41 |
| 2 | Alerta de previsão toda zero calculado no frontend, também na tabela do lote | #38 |
| 3 | Changelog renderizado no app a partir de `GET /changelog` | #46 |
| 4 | `docs_dir: docs/guia/`; ADRs injetados no build; sem duplicar relatórios nem endpoints | #47 |
| 5 | Tokens compartilhados em `design/tokens.css`; escuro derivado só na documentação | #42, #47 |
| 6 | Upload único sem barra de progresso em bytes; LLM com select de provedor + modelo e botão mostrar/ocultar | #43, #44 |
| 7 | Criar issues, ADR, glossário e registro sem entregar o plano no chat | este registro |

Decisões minhas, sem pergunta explícita (revisáveis): a ordem das issues (seção 1); a janela recente do histórico no gráfico (#38); as tarefas poe `docs` e `docs-build` e a porta 8001 (#47); o grupo de dependências `docs` (#47); a ausência de Docker declarada como lacuna (#50).

## 4. Proposta de interface (resumo)

- **Hierarquia:** 01 Escolha a série e gere a previsão; 02 Demanda ao longo do tempo; 03 Pedir previsões em lote; 04 Comparação de SKUs; 05 Recomendações; 06 Enviar pedidos novos. A ordem final é a decidir em #42 (hoje: previsão, gráfico, envio de pedidos, pedir previsões, comparação, recomendações).
- **Cabeçalho:** Documentação, Swagger, Changelog, MLflow, com o mesmo estilo de link.
- **Gráfico:** eixo temporal, janela recente do histórico, linha contínua (histórico) e tracejada com marcadores (previsão), faixa do horizonte com rótulo "Início da previsão", intervalos só quando existirem, tooltip com data e valor, alerta de zero no canto do gráfico com tooltip. Os textos são os pedidos: "A previsão foi gerada, porém todos os valores previstos para a janela selecionada são iguais a zero." e "Isso significa que o modelo estimou demanda zero para todos os períodos futuros da janela de previsão. Consulte o histórico e os dados de entrada para contextualizar esse resultado."
- **Estados:** carregando, sem dados, erro e previsão toda zero são distintos.

## 5. Plano de documentação (MkDocs Material, `docs/guia/`)

- `index.md` (propósito e público), `negocio/` (contexto, glossário apontando para `GLOSSARY.md`), `arquitetura/` (visão geral, fluxos, armazenamento), `funcional/` (regras por funcionalidade), `ciencia-de-dados/` (dados, partições, candidatos, backtest, seleção, intervalos, confiança, reajuste, avaliação final, por SKU e granularidade), `operacao/` (instalação, configuração, execução, testes, logs, retreino, troubleshooting), `decisoes/` (ADRs do build), `rastreabilidade.md`. Changelog e endpoints: só links para `CHANGELOG.md`/`/changelog` e `/docs`.
- Fontes por página: ver as issues #48 a #50.

## 6. Pendências e questões abertas

- **Reajuste real (#40):** altera `data/mlflow` versionado; precisa de aprovação no momento. Antes, confirmar se `reajustar_serie` promove o `champion` automaticamente (o ADR 0011 diz que sim; não executado aqui).
- **Premissa "um modelo por SKU e granularidade":** os nomes `demanda-item-x-diaria|semanal` e os 8 aliases `champion` existem no registro (verificado); a recusa de série errada e o hash precisam de leitura de `api/modelos.py` em #49.
- **Confiança:** a memória do projeto diz que pode sair da solução se o #12 mostrar que é inútil; verificar o estado atual em #49 antes de documentá-la como vigente.
- **Tamanho máximo de upload:** o backend não foi lido; definir em #43.
- **Ferramenta de teste de acessibilidade no frontend:** não há teste de frontend no projeto; decidir em #45 se adota alguma.
- **Publicação da documentação:** fora do escopo; sem destino definido.
- **LLM real e e-mail:** nunca exercitados (README, #26); a documentação deve dizê-lo.
- **Verificação visual em navegador:** cabe ao usuário, como na #26.
- **Referências externas** (scikit-learn, FastAPI, MkDocs Material): usadas apenas como guia editorial, sem consulta de texto nesta rodada.

## 7. Reprodução do diagnóstico D1

```bash
uv run python - <<'PY'
from fastapi.testclient import TestClient
from case_mr_health.api.app import criar_app
with TestClient(criar_app()) as c:
    for g, ref, h in [('diaria','2021-09-01',7), ('diaria','2021-08-18',7), ('semanal','2021-08-23',2)]:
        r = c.post('/predicoes', json=dict(sku='item A', granularidade=g, data_referencia=ref, horizonte=h))
        print(g, ref, h, r.status_code)
PY
```

## Fechamento (#48 e #51)

A issue #48 preencheu as páginas de negócio, arquitetura e funcional; o diagrama Mermaid e os links para ADRs fazem parte do guia. A revisão #51 consolidou rastreabilidade em `docs/guia/rastreabilidade.md`, incluindo remoção de confiança, exclusão de ARIMA/Prophet sem ADR atualizado, opção `--demonstracao` ausente, identificador `hash_dados = base`, divergências do Swagger e lacunas de e-mail real/deploy. Detalhes em `docs/relatorio/onda6/48.md` e `51.md`.

Checklist visual para navegador está em `issues/51.md`; requer conferência humana, não foi declarado como executado. Build visual não substitui o teste funcional no navegador.

Lint passou; build estrito passou após corrigir links. Resultado de `test-rapido` e revisão de critérios será registrado em `docs/relatorio/onda6/51.md`. Nenhum treino, reajuste ou escrita em artefatos de modelos foi realizado. Fragmentos pendentes incluem itens `adicionado`; sugestão de release: 0.6.0 (MINOR) sobre 0.5.0, sem compilar changelog ou mudar versão.
