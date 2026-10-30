<script>
  // Comparação da demanda entre SKUs e download do sumário XLSX (#25).
  let { api, sku, granularidade, skus } = $props();

  const cores = ['#739354', '#d3944f', '#3d6f8e', '#a0527c'];
  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const fmtData = (valor) => new Intl.DateTimeFormat('pt-BR').format(new Date(`${valor}T12:00:00`));

  let series = $state([]);
  let erro = $state('');
  let carregando = $state(false);
  let limitarSku = $state(true);
  let limitarGranularidade = $state(true);
  let baixando = $state(false);

  let rotuloGranularidade = $derived(granularidade === 'diaria' ? 'diária' : 'semanal');
  let completo = $derived(!limitarSku && !limitarGranularidade);
  let escopo = $derived(
    completo
      ? 'Conjunto completo: todos os SKUs e as duas granularidades'
      : `Filtrado: ${limitarSku ? sku : 'todos os SKUs'} · ${limitarGranularidade ? rotuloGranularidade : 'diária e semanal'}`,
  );

  async function carregar(granul) {
    erro = '';
    carregando = true;
    try {
      const respostas = await Promise.all(
        skus.map(async (item) => {
          const resposta = await fetch(`${api}/series/${encodeURIComponent(item)}/${granul}`);
          const corpo = await resposta.json();
          if (!resposta.ok) throw new Error(corpo.mensagem ?? `Não foi possível carregar ${item}.`);
          return { sku: item, pontos: corpo.pontos };
        }),
      );
      series = respostas;
    } catch (falha) {
      erro = falha.message;
      series = [];
    } finally {
      carregando = false;
    }
  }

  $effect(() => {
    carregar(granularidade);
  });

  let datas = $derived([...new Set(series.flatMap((s) => s.pontos.map((p) => p.data)))].sort());
  let teto = $derived(Math.max(1, ...series.flatMap((s) => s.pontos.map((p) => p.quantidade))) * 1.1);
  const x = (indice, total) => (total <= 1 ? 40 : 40 + (indice * 820) / (total - 1));
  const y = (valor) => 245 - (valor / teto) * 205;
  let linhas = $derived(
    series.map((s, i) => {
      const porData = new Map(s.pontos.map((p) => [p.data, p.quantidade]));
      const pontos = datas
        .map((data, indice) => (porData.has(data) ? `${x(indice, datas.length)},${y(porData.get(data))}` : null))
        .filter(Boolean)
        .join(' ');
      return { sku: s.sku, cor: cores[i % cores.length], pontos };
    }),
  );

  async function baixar() {
    erro = '';
    baixando = true;
    try {
      const parametros = new URLSearchParams();
      if (limitarSku) parametros.set('sku', sku);
      if (limitarGranularidade) parametros.set('granularidade', granularidade);
      const resposta = await fetch(`${api}/previsoes/exportacao.xlsx?${parametros}`);
      if (!resposta.ok) {
        const corpo = await resposta.json();
        throw new Error(corpo.mensagem ?? 'Não foi possível gerar o sumário.');
      }
      const endereco = URL.createObjectURL(await resposta.blob());
      const link = document.createElement('a');
      link.href = endereco;
      link.download = `sumario-${completo ? 'completo' : 'filtrado'}.xlsx`;
      link.click();
      URL.revokeObjectURL(endereco);
    } catch (falha) {
      erro = falha.message;
    } finally {
      baixando = false;
    }
  }
</script>

<section class="card comparacao" aria-label="Comparação entre SKUs">
  <div class="cabecalho">
    <div><h2>Comparar SKUs</h2><p>Demanda {rotuloGranularidade} da rede, todos os SKUs no mesmo gráfico.</p></div>
    <div class="legenda">
      {#each linhas as linha}<span><i style:background={linha.cor}></i>{linha.sku}</span>{/each}
    </div>
  </div>

  {#if erro}<div class="error" role="alert">{erro}</div>{/if}
  {#if carregando}
    <p class="nota">Carregando…</p>
  {:else if datas.length}
    <svg viewBox="0 0 900 290" role="img" aria-label="Gráfico de linhas com a demanda de cada SKU">
      <line x1="40" y1="245" x2="860" y2="245" class="axis" />
      <line x1="40" y1="40" x2="40" y2="245" class="axis" />
      <text x="30" y="48" class="tick" text-anchor="end">{fmt.format(teto / 1.1)}</text>
      <text x="30" y="250" class="tick" text-anchor="end">0</text>
      {#each linhas as linha}<polyline points={linha.pontos} fill="none" stroke={linha.cor} stroke-width="2.5" stroke-linejoin="round" />{/each}
      <text x="40" y="274" class="tick">{fmtData(datas[0])}</text>
      <text x="860" y="274" class="tick" text-anchor="end">{fmtData(datas.at(-1))}</text>
    </svg>
  {/if}

  <div class="sumario">
    <strong>Sumário XLSX das previsões</strong>
    <label><input type="checkbox" bind:checked={limitarSku} /> Só o SKU selecionado ({sku})</label>
    <label><input type="checkbox" bind:checked={limitarGranularidade} /> Só a granularidade selecionada ({rotuloGranularidade})</label>
    <p class="escopo" data-completo={completo}>Escopo: {escopo}</p>
    <button type="button" onclick={baixar} disabled={baixando}>{baixando ? 'Gerando…' : 'Baixar sumário (.xlsx)'}</button>
  </div>
</section>

<style>
  .comparacao { margin-top: 24px; padding: 24px 25px; }
  .cabecalho { display: flex; justify-content: space-between; gap: 18px; align-items: start; flex-wrap: wrap; }
  .cabecalho p, .nota { color: #74837d; font-size: 12px; margin: 0; }
  .legenda { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: #5b6b64; padding-top: 7px; }
  .legenda i { display: inline-block; width: 14px; height: 3px; margin-right: 5px; vertical-align: middle; }
  .sumario { margin-top: 18px; padding-top: 16px; border-top: 1px solid #e6ebe6; display: grid; gap: 8px; font-size: 12px; }
  .escopo { margin: 4px 0; font-weight: 600; color: #234d3e; }
  .escopo[data-completo='false'] { color: #9a5f1f; }
  button { justify-self: start; height: 38px; padding: 0 16px; border: 0; border-radius: 8px; background: #234d3e; color: #fff; font-weight: 600; font-size: 12px; cursor: pointer; }
  button:disabled { opacity: .55; cursor: wait; }
</style>
