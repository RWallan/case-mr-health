# Dashboard de previsão

Frontend simples em Svelte e Vite, sem roteador ou biblioteca de gráficos.

```bash
npm install
npm run dev
npm run build
```

O backend deve estar rodando em `http://localhost:8000`. Para mudar os
endereços, crie `.env.local` com `VITE_API_URL` e `VITE_MLFLOW_URL`.
O dashboard usa apenas a série de desenvolvimento e as rotas de previsão;
nenhum treino é iniciado pela tela.
