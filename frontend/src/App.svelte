<script>
  import EntradaPrevisoes from './EntradaPrevisoes.svelte';
  import ComparacaoSkus from './ComparacaoSkus.svelte';
  import LinksApi from './LinksApi.svelte';
  import Recomendacoes from './Recomendacoes.svelte';
  const api = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
  const mlflow = import.meta.env.VITE_MLFLOW_URL ?? 'http://localhost:5000';
  const skus = ['item A', 'item B', 'item C', 'item D'];
  const granularidades = ['diaria', 'semanal'];

  let sku = $state('item A');
  let granularidade = $state('diaria');
  let horizonte = $state(7);
  let dataReferencia = $state('');
  let historico = $state([]);
  let previsao = $state(null);
  let erro = $state('');
  let carregando = $state(false);
  let arquivoPedidos = $state(null);
  let arquivoItens = $state(null);
  let enviando = $state(false);
  let atualizacao = $state(null);
  let errosEnvio = $state([]);
  let mensagemEnvio = $state('');

  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const fmtData = (valor) => new Intl.DateTimeFormat('pt-BR').format(new Date(`${valor}T12:00:00`));

  async function carregarSerie() {
    erro = '';
    previsao = null;
    carregando = true;
    try {
      const resposta = await fetch(
        `${api}/series/${encodeURIComponent(sku)}/${granularidade}`,
      );
      const corpo = await resposta.json();
      if (!resposta.ok) throw new Error(corpo.mensagem ?? 'Não foi possível carregar o histórico.');
      historico = corpo.pontos;
      dataReferencia = historico.at(-1)?.data ?? '';
      horizonte = granularidade === 'diaria' ? 7 : 2;
    } catch (falha) {
      erro = falha.message;
      historico = [];
    } finally {
      carregando = false;
    }
  }

  async function buscar(event) {
    event?.preventDefault();
    erro = '';
    previsao = null;
    carregando = true;
    try {
      const resposta = await fetch(`${api}/predicoes`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ sku, granularidade, data_referencia: dataReferencia, horizonte }),
      });
      const corpo = await resposta.json();
      if (!resposta.ok) throw new Error(corpo.mensagem ?? 'Não foi possível gerar a previsão.');
      previsao = corpo;
    } catch (falha) {
      erro = falha.message;
    } finally {
      carregando = false;
    }
  }

  const estadosFinais = ['concluida', 'concluida_com_erros', 'falhou'];
  const rotuloEstado = {
    em_andamento: 'Reajustando os modelos…',
    concluida: 'Atualização concluída',
    concluida_com_erros: 'Concluída, com erros em algumas séries',
    falhou: 'Falhou: nenhuma série foi reajustada',
  };
  const pausa = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

  async function enviarPedidos(event) {
    event.preventDefault();
    errosEnvio = [];
    mensagemEnvio = '';
    atualizacao = null;
    enviando = true;
    try {
      const corpo = new FormData();
      corpo.append('pedidos', arquivoPedidos[0]);
      corpo.append('itens', arquivoItens[0]);
      const resposta = await fetch(`${api}/dados/pedidos`, { method: 'POST', body: corpo });
      const dados = await resposta.json();
      if (!resposta.ok) {
        mensagemEnvio = dados.mensagem ?? 'Não foi possível enviar os pedidos.';
        errosEnvio = dados.detalhes ?? [];
        return;
      }
      atualizacao = dados;
      await acompanhar(dados.id);
    } catch (falha) {
      mensagemEnvio = falha.message;
    } finally {
      enviando = false;
    }
  }

  async function acompanhar(id) {
    while (true) {
      await pausa(1500);
      const resposta = await fetch(`${api}/dados/atualizacoes/${id}`);
      atualizacao = await resposta.json();
      if (estadosFinais.includes(atualizacao.estado)) break;
    }
    // O histórico e a previsão passam a partir dos pedidos novos.
    await carregarSerie();
    await buscar();
  }

  $effect(() => {
    sku;
    granularidade;
    carregarSerie();
  });

  let valoresGrafico = $derived([
    ...historico.map((ponto) => ponto.quantidade),
    ...(previsao?.periodos ?? []).map((ponto) => ponto.quantidade_prevista),
    ...(previsao?.periodos ?? []).flatMap((ponto) => [
      ponto.limite_inferior_95 ?? 0,
      ponto.limite_superior_95 ?? ponto.quantidade_prevista,
    ]),
  ]);
  let teto = $derived(Math.max(1, ...valoresGrafico) * 1.18);
  let pontos = $derived([...historico, ...(previsao?.periodos ?? [])]);
  let linhaHistorico = $derived(
    historico.map((ponto, indice) => `${x(indice, pontos.length)},${y(ponto.quantidade)}`).join(' '),
  );
  let linhaPrevisao = $derived(
    (previsao?.periodos ?? []).map((ponto, indice) => `${x(historico.length + indice, pontos.length)},${y(ponto.quantidade_prevista)}`).join(' '),
  );

  function x(indice, total) {
    return total <= 1 ? 40 : 40 + (indice * 820) / (total - 1);
  }

  function y(valor) {
    return 245 - (valor / teto) * 205;
  }
</script>

<svelte:head>
  <meta name="description" content="Histórico e previsão da demanda da rede MR. HEALTH." />
</svelte:head>

<div class="shell">
  <header class="topbar">
    <a class="brand" href="/" aria-label="MR. HEALTH, início">
      <span class="brand-mark">+</span>
      <span>MR.<strong>HEALTH</strong></span>
    </a>
    <div class="topbar-right">
      <span class="network-label"><span class="status-dot"></span> Visão da rede</span>
      <LinksApi {api} />
      <a class="link" href={mlflow} target="_blank" rel="noreferrer">Abrir MLflow <span aria-hidden="true">↗</span></a>
    </div>
  </header>

  <main>
    <section class="intro">
      <div>
        <p class="eyebrow">PLANEJAMENTO DE DEMANDA</p>
        <h1>Veja o que vem pela frente.</h1>
        <p class="intro-copy">Compare as vendas recentes com a previsão para a rede inteira.</p>
      </div>
      <div class="source-badge"><span>PREVISÃO</span><strong>Da rede</strong></div>
    </section>

    <section class="workspace" aria-label="Previsão de demanda">
      <aside class="controls card">
        <div class="section-heading">
          <span class="step">01</span>
          <div><h2>Escolha a série</h2><p>Defina o produto e o período.</p></div>
        </div>
        <label class="rotulo" for="sku">SKU</label>
        <select id="sku" class="campo" bind:value={sku}>
          {#each skus as opcao}<option value={opcao}>{opcao}</option>{/each}
        </select>
        <span class="rotulo" id="rotulo-granularidade">Granularidade</span>
        <div class="segmented" role="group" aria-labelledby="rotulo-granularidade">
          {#each granularidades as opcao}
            <button type="button" class:active={granularidade === opcao} aria-pressed={granularidade === opcao} onclick={() => (granularidade = opcao)}>{opcao === 'diaria' ? 'Diária' : 'Semanal'}</button>
          {/each}
        </div>
        <form onsubmit={buscar}>
          <label class="rotulo" for="referencia">Último período conhecido</label>
          <input id="referencia" class="campo" type="date" bind:value={dataReferencia} required />
          <label class="rotulo" for="horizonte">Períodos a prever</label>
          <input id="horizonte" class="campo" type="number" min="1" max={granularidade === 'diaria' ? 14 : 2} bind:value={horizonte} required />
          <button class="btn btn-bloco" type="submit" disabled={carregando || !dataReferencia} aria-busy={carregando}>
            {carregando ? 'Carregando…' : 'Gerar previsão'} <span aria-hidden="true">→</span>
          </button>
        </form>
        <p class="limits-note">Limite validado: {granularidade === 'diaria' ? '14 dias' : '2 semanas'} após o fim do treino.</p>
      </aside>

      <section class="results card" aria-live="polite">
        <div class="results-heading">
          <div class="section-heading">
            <span class="step">02</span>
            <div><h2>Demanda ao longo do tempo</h2><p>{sku} · {granularidade === 'diaria' ? 'Diária' : 'Semanal'} · quantidade na rede</p></div>
          </div>
          <div class="legend"><span class="legend-history"></span> Histórico <span class="legend-forecast"></span> Previsão <span class="legend-interval"></span> Intervalo 80% / 95%</div>
        </div>

        {#if erro}<div class="alerta alerta-erro" role="alert">{erro}</div>{/if}
        {#if historico.length}
          <div class="chart-wrap">
            <svg viewBox="0 0 900 290" role="img" aria-label="Gráfico do histórico e da previsão de vendas">
              <line x1="40" y1="245" x2="860" y2="245" class="axis" />
              <line x1="40" y1="40" x2="40" y2="245" class="axis" />
              <line x1="40" y1="143" x2="860" y2="143" class="gridline" />
              <text x="30" y="48" class="tick" text-anchor="end">{fmt.format(teto / 1.18)}</text>
              <text x="30" y="250" class="tick" text-anchor="end">0</text>
              {#if historico.length > 1}<polyline points={linhaHistorico} class="history-line" />{/if}
              {#if previsao?.periodos?.length}
                {#if historico.length}<line x1={x(historico.length - 1, pontos.length)} y1="40" x2={x(historico.length - 1, pontos.length)} y2="245" class="split-line" />{/if}
                <polyline points={linhaPrevisao} class="forecast-line" />
                {#each previsao.periodos as periodo, indice}
                    <line x1={x(historico.length + indice, pontos.length)} y1={y(periodo.limite_superior_95 ?? periodo.quantidade_prevista)} x2={x(historico.length + indice, pontos.length)} y2={y(periodo.limite_inferior_95 ?? 0)} class="interval-95" />
                    <line x1={x(historico.length + indice, pontos.length)} y1={y(periodo.limite_superior_80 ?? periodo.quantidade_prevista)} x2={x(historico.length + indice, pontos.length)} y2={y(periodo.limite_inferior_80 ?? 0)} class="interval-80" />
                  <circle cx={x(historico.length + indice, pontos.length)} cy={y(periodo.quantidade_prevista)} r="5" class="forecast-point" />
                {/each}
              {/if}
              {#if historico.length}
                <text x="40" y="274" class="tick">{fmtData(historico[0].data)}</text>
                <text x="860" y="274" class="tick" text-anchor="end">{fmtData(pontos.at(-1).data)}</text>
              {/if}
            </svg>
          </div>
          <div class="chart-footnote"><span>—</span> Faixa externa mostra o intervalo de 95%. A previsão começa após a linha pontilhada.</div>
        {:else}
          <div class="empty-state"><div class="empty-icon">⌁</div><h3>Seu histórico aparecerá aqui</h3><p>O gráfico mostra as vendas até o último período disponível e a previsão gerada.</p></div>
        {/if}

        {#if previsao}
          <div class="forecast-summary">
            <div><span class="summary-label">PREVISÃO PARA {previsao.periodos.length} PERÍODOS</span><strong>{fmt.format(previsao.periodos.reduce((soma, item) => soma + item.quantidade_prevista, 0))}<small> unidades</small></strong></div>
            <div><span class="summary-label">VALOR ESTIMADO</span><strong>R$ {fmt.format(previsao.periodos.reduce((soma, item) => soma + item.valor_previsto, 0))}</strong></div>
            <div><span class="summary-label">MODELO</span><strong>Versão {previsao.versao_modelo}</strong>{#if previsao.origem_modelo === 'atualizacao'}<small>Reajustada com pedidos novos; sem métrica fora da amostra.</small>{/if}</div>
          </div>
          <p class="interval-note">Os intervalos são apresentados por período e não devem ser somados entre períodos.</p>
        {/if}
      </section>
    </section>

    <EntradaPrevisoes />
    <ComparacaoSkus {api} {sku} {granularidade} {skus} />
    <Recomendacoes {api} {skus} />

    <section class="card update" aria-label="Atualizar dados">
      <div class="section-heading">
        <span class="step">06</span>
        <div><h2>Enviar pedidos novos</h2><p>Os modelos são reajustados com o histórico atualizado.</p></div>
      </div>
      <form onsubmit={enviarPedidos}>
        <label class="rotulo" for="pedidos">Planilha de pedidos (.xlsx)</label>
        <input id="pedidos" class="campo" type="file" accept=".xlsx" bind:files={arquivoPedidos} required />
        <label class="rotulo" for="itens">Planilha de itens de pedido (.xlsx)</label>
        <input id="itens" class="campo" type="file" accept=".xlsx" bind:files={arquivoItens} required />
        <button class="btn btn-bloco" type="submit" disabled={enviando || !arquivoPedidos?.length || !arquivoItens?.length} aria-busy={enviando}>
          {enviando ? 'Enviando…' : 'Enviar e reajustar'} <span aria-hidden="true">→</span>
        </button>
      </form>
      {#if mensagemEnvio}
        <div class="alerta alerta-erro" role="alert">
          {mensagemEnvio}
          {#if errosEnvio.length}
            <table class="tabela">
              <thead><tr><th>Onde</th><th>Problema</th></tr></thead>
              <tbody>{#each errosEnvio as item}<tr><td>{item.campo}</td><td>{item.mensagem}</td></tr>{/each}</tbody>
            </table>
          {/if}
        </div>
      {/if}
      {#if atualizacao}
        <div class="update-status" aria-live="polite">
          <strong>{rotuloEstado[atualizacao.estado]}</strong>
          <p>{atualizacao.pedidos_novos} pedidos novos · {atualizacao.itens_novos} itens · dados até {fmtData(atualizacao.ultimo_dia)}</p>
          {#if atualizacao.series.length}
            <table class="tabela">
              <thead><tr><th>Série</th><th>Situação</th><th>Versão</th></tr></thead>
              <tbody>
                {#each atualizacao.series as serie}
                  <tr>
                    <td>{serie.sku} · {serie.granularidade === 'diaria' ? 'diária' : 'semanal'}</td>
                    <td>{serie.estado === 'reajustada' ? 'Reajustada' : serie.estado === 'ignorada' ? 'Sem modelo para reajustar' : `Falhou: ${serie.erro}`}</td>
                    <td>{serie.versao_nova ? `${serie.versao_anterior} → ${serie.versao_nova}` : '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
          <p class="interval-note">{atualizacao.aviso}</p>
        </div>
      {/if}
    </section>

    <footer><span>MR. HEALTH · Planejamento de demanda</span><span>Previsões da rede · Só o envio de pedidos novos reajusta os modelos</span></footer>
  </main>
</div>
