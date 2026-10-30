<script>
  import AvisoZero from './AvisoZero.svelte';
  import FormularioPrevisao from './FormularioPrevisao.svelte';
  import Upload from './Upload.svelte';
  import { campoDoErro, erroDoLote } from './formulario.js';
  import { previsaoTodaZero } from './grafico.js';
  const api = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
  const skus = ['item A', 'item B', 'item C', 'item D'];

  let sku = $state('item A');
  let granularidade = $state('diaria');
  let erroForm = $state(null);
  let arquivo = $state(null);
  let enviando = $state(false);
  let mensagem = $state('');
  let erros = $state([]);
  let resultados = $state([]);

  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const rotulo = (g) => (g === 'diaria' ? 'diária' : 'semanal');

  // Envia ao backend e normaliza erros {campo, mensagem} (campo traz a linha em XLSX).
  async function enviar(requisicao, manual = false) {
    mensagem = '';
    erroForm = null;
    erros = [];
    resultados = [];
    enviando = true;
    try {
      const resposta = await requisicao();
      const corpo = await resposta.json();
      if (!resposta.ok) {
        mensagem = corpo.mensagem ?? 'Não foi possível gerar as previsões.';
        erros = corpo.detalhes ?? [];
        if (manual) erroForm = erroDoLote(corpo);
        return;
      }
      resultados = corpo.resultados;
    } catch (falha) {
      mensagem = falha.message;
    } finally {
      enviando = false;
    }
  }

  function enviarManual(item) {
    return enviar(
      () =>
        fetch(`${api}/predicoes/lote`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ itens: [item] }),
        }),
      true,
    );
  }

  function enviarPlanilha(event) {
    event.preventDefault();
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return enviar(() => fetch(`${api}/predicoes/lote/xlsx`, { method: 'POST', body: corpo }));
  }
</script>

<section class="card update" aria-label="Pedir previsões">
  <div class="section-heading">
    <span class="step">03</span>
    <div><h2>Pedir previsões</h2><p>Preencha uma solicitação ou envie uma planilha com várias.</p></div>
  </div>

  <FormularioPrevisao id="entrada" {skus} bind:sku bind:granularidade carregando={enviando} erro={erroForm} onenviar={enviarManual} />

  <form onsubmit={enviarPlanilha}>
    <Upload id="entrada-arquivo" rotulo="Planilha de solicitações (.xlsx)" bind:arquivo estado={enviando ? 'processando' : resultados.length ? 'sucesso' : 'ocioso'} mensagemSucesso="Planilha processada." />
    <a class="link" href={`${api}/predicoes/lote/template.xlsx`} download>Baixar o template (.xlsx)</a>
    <button class="btn btn-bloco" type="submit" disabled={enviando || !arquivo} aria-busy={enviando}>
      {enviando ? 'Enviando…' : 'Enviar planilha'} <span aria-hidden="true">→</span>
    </button>
  </form>

  {#if mensagem && !campoDoErro(erroForm)}
    <div class="alerta alerta-erro" role="alert">
      {mensagem}
      {#if erros.length}
        <table class="tabela">
          <thead><tr><th>Campo / linha</th><th>Problema</th></tr></thead>
          <tbody>{#each erros as item}<tr><td>{item.campo}</td><td>{item.mensagem}</td></tr>{/each}</tbody>
        </table>
      {/if}
    </div>
  {/if}

  {#if resultados.length}
    <div class="update-status" aria-live="polite">
      <strong>{resultados.length} previsão(ões) gerada(s)</strong>
      <table class="tabela">
        <thead><tr><th>Linha</th><th>Série</th><th>Períodos</th><th>Total previsto</th></tr></thead>
        <tbody>
          {#each resultados as item}
            <tr>
              <td>{item.linha ?? item.indice + 1}</td>
              <td>{item.previsao.sku} · {rotulo(item.previsao.granularidade)}</td>
              <td>{item.previsao.periodos.length}</td>
              <td>
                {fmt.format(item.previsao.periodos.reduce((soma, p) => soma + p.quantidade_prevista, 0))} unidades
                {#if previsaoTodaZero(item.previsao.periodos)}<AvisoZero rotulo="Previsão toda zero" id={`dica-zero-lote-${item.indice}`} />{/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
