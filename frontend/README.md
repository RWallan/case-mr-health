# Dashboard de previsão

Frontend simples em Svelte e Vite, sem roteador ou biblioteca de gráficos.

```bash
npm install
npm run dev
npm run build
```

O backend deve estar rodando em `http://localhost:8000`. Para mudar os
endereços, crie `.env.local` com `VITE_API_URL`, `VITE_MLFLOW_URL` e `VITE_DOCS_URL` (padrão
`http://localhost:8001`, destino do link "Documentação").
O dashboard lê a série completa da base e as rotas de previsão. A seção
"Enviar pedidos novos" manda as duas planilhas para `POST /dados/pedidos`,
mostra os erros com planilha e linha, acompanha o reajuste dos modelos e
atualiza o gráfico ao concluir (ADR 0011). Nenhuma outra ação da tela treina.

O gráfico de previsão (`GraficoPrevisao.svelte`) monta a série e decide o alerta de previsão toda zero em `src/grafico.js`, módulo puro com testes sem navegador: `uv run poe test-frontend` (usa `node --test`).
