<script>
  const api = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
  const skus = ['item A', 'item B', 'item C', 'item D'];
  const maxHorizonte = { diaria: 14, semanal: 2 };

  let sku = $state('item A');
  let granularidade = $state('diaria');
  let dataReferencia = $state('');
  let horizonte = $state(7);
  let arquivo = $state(null);
  let enviando = $state(false);
  let mensagem = $state('');
  let erros = $state([]);
  let resultados = $state([]);

  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const rotulo = (g) => (g === 'diaria' ? 'diária' : 'semanal');

  // Envia ao backend e normaliza erros {campo, mensagem} (campo traz a linha em XLSX).
  async function enviar(requisicao) {
    mensagem = '';
    erros = [];
    resultados = [];
    enviando = true;
    try {
      const resposta = await requisicao();
      const corpo = await resposta.json();
      if (!resposta.ok) {
        mensagem = corpo.mensagem ?? 'Não foi possível gerar as previsões.';
        erros = corpo.detalhes ?? [];
        return;
      }
      resultados = corpo.resultados;
    } catch (falha) {
      mensagem = falha.message;
    } finally {
      enviando = false;
    }
  }

  function enviarManual(event) {
    event.preventDefault();
    return enviar(() =>
      fetch(`${api}/predicoes/lote`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          itens: [{ sku, granularidade, data_referencia: dataReferencia, horizonte }],
        }),
      }),
    );
  }

  function enviarPlanilha(event) {
    event.preventDefault();
    const corpo = new FormData();
    corpo.append('arquivo', arquivo[0]);
    return enviar(() => fetch(`${api}/predicoes/lote/xlsx`, { method: 'POST', body: corpo }));
  }
</script>

<section class="card update" aria-label="Pedir previsões">
  <div class="section-heading">
    <span class="step">04</span>
    <div><h2>Pedir previsões</h2><p>Preencha uma solicitação ou envie uma planilha com várias.</p></div>
  </div>

  <form onsubmit={enviarManual}>
    <label for="entrada-sku">SKU</label>
    <select id="entrada-sku" bind:value={sku} required>
      {#each skus as opcao}<option value={opcao}>{opcao}</option>{/each}
    </select>
    <label for="entrada-granularidade">Granularidade</label>
    <select id="entrada-granularidade" bind:value={granularidade} required>
      <option value="diaria">Diária</option>
      <option value="semanal">Semanal</option>
    </select>
    <label for="entrada-data">Último período conhecido</label>
    <input id="entrada-data" type="date" bind:value={dataReferencia} pattern={'\\d{4}-\\d{2}-\\d{2}'} required />
    <label for="entrada-horizonte">Períodos a prever (1 a {maxHorizonte[granularidade]})</label>
    <input id="entrada-horizonte" type="number" min="1" max={maxHorizonte[granularidade]} step="1" bind:value={horizonte} required />
    <button class="primary" type="submit" disabled={enviando}>
      {enviando ? 'Enviando…' : 'Gerar previsão'} <span aria-hidden="true">→</span>
    </button>
  </form>

  <form onsubmit={enviarPlanilha}>
    <label for="entrada-arquivo">Planilha de solicitações (.xlsx)</label>
    <input id="entrada-arquivo" type="file" accept=".xlsx" bind:files={arquivo} required />
    <a href={`${api}/predicoes/lote/template.xlsx`} download>Baixar o template (.xlsx)</a>
    <button class="primary" type="submit" disabled={enviando || !arquivo?.length}>
      {enviando ? 'Enviando…' : 'Enviar planilha'} <span aria-hidden="true">→</span>
    </button>
  </form>

  {#if mensagem}
    <div class="error" role="alert">
      {mensagem}
      {#if erros.length}
        <table class="erros">
          <thead><tr><th>Campo / linha</th><th>Problema</th></tr></thead>
          <tbody>{#each erros as item}<tr><td>{item.campo}</td><td>{item.mensagem}</td></tr>{/each}</tbody>
        </table>
      {/if}
    </div>
  {/if}

  {#if resultados.length}
    <div class="update-status" aria-live="polite">
      <strong>{resultados.length} previsão(ões) gerada(s)</strong>
      <table class="erros">
        <thead><tr><th>Linha</th><th>Série</th><th>Períodos</th><th>Total previsto</th></tr></thead>
        <tbody>
          {#each resultados as item}
            <tr>
              <td>{item.linha ?? item.indice + 1}</td>
              <td>{item.previsao.sku} · {rotulo(item.previsao.granularidade)}</td>
              <td>{item.previsao.periodos.length}</td>
              <td>{fmt.format(item.previsao.periodos.reduce((soma, p) => soma + p.quantidade_prevista, 0))} unidades</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
