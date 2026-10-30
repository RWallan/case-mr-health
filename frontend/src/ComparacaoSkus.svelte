<script>
  // Comparação da demanda entre SKUs e download do sumário XLSX (#25).
  let { api, sku, granularidade, skus } = $props();

  const cores = ['var(--cor-serie-1)', 'var(--cor-serie-2)', 'var(--cor-serie-3)', 'var(--cor-serie-4)'];
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
    <div class="section-heading"><span class="step">04</span><div><h2>Comparar SKUs</h2><p>Demanda {rotuloGranularidade} da rede, todos os SKUs no mesmo gráfico.</p></div></div>
    <div class="legenda">
      {#each linhas as linha}<span><i style:background={linha.cor}></i>{linha.sku}</span>{/each}
    </div>
  </div>

  {#if erro}<div class="alerta alerta-erro" role="alert">{erro}</div>{/if}
  {#if carregando}
    <p class="carregando" role="status">Carregando…</p>
  {:else if datas.length}
    <!-- Em telas estreitas o gráfico mantém largura mínima e rola dentro do contêiner, com teclado. -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex (região rolável precisa de foco no teclado) -->
    <div class="rolagem" role="region" aria-label="Gráfico de linhas com a demanda de cada SKU" tabindex="0">
    <svg viewBox="0 0 900 290" role="img" aria-label={`Demanda ${rotuloGranularidade} de ${linhas.map((l) => l.sku).join(', ')}, de ${fmtData(datas[0])} a ${fmtData(datas.at(-1))}`}>
      <line x1="40" y1="245" x2="860" y2="245" class="axis" />
      <line x1="40" y1="40" x2="40" y2="245" class="axis" />
      <text x="30" y="48" class="tick" text-anchor="end">{fmt.format(teto / 1.1)}</text>
      <text x="30" y="250" class="tick" text-anchor="end">0</text>
      {#each linhas as linha}<polyline points={linha.pontos} fill="none" style:stroke={linha.cor} stroke-width="2.5" stroke-linejoin="round" />{/each}
      <text x="40" y="274" class="tick">{fmtData(datas[0])}</text>
      <text x="860" y="274" class="tick" text-anchor="end">{fmtData(datas.at(-1))}</text>
    </svg>
    </div>
  {/if}

  <div class="sumario">
    <strong>Sumário XLSX das previsões</strong>
    <label class="opcao"><input type="checkbox" bind:checked={limitarSku} /> Só o SKU selecionado ({sku})</label>
    <label class="opcao"><input type="checkbox" bind:checked={limitarGranularidade} /> Só a granularidade selecionada ({rotuloGranularidade})</label>
    <p class="escopo" data-completo={completo} aria-live="polite">Escopo: {escopo}</p>
    <button class="btn btn-secundario" type="button" onclick={baixar} disabled={baixando} aria-busy={baixando}>{baixando ? 'Gerando…' : 'Baixar sumário (.xlsx)'}</button>
  </div>
</section>

<style>
  .comparacao { margin-top: 24px; padding: 24px 25px; }
  .cabecalho { display: flex; justify-content: space-between; gap: 18px; align-items: start; flex-wrap: wrap; }
  .cabecalho p { color: var(--cor-texto-suave); font-size: var(--texto-xs); margin: 0; }
  .legenda { display: flex; gap: 14px; flex-wrap: wrap; font-size: var(--texto-xs); color: var(--cor-texto-secundario); padding-top: 7px; }
  .rolagem { max-width: 100%; overflow-x: auto; }
  .rolagem:focus-visible { outline: 3px solid var(--cor-foco); outline-offset: 2px; }
  .rolagem svg { display: block; width: 100%; min-width: 560px; height: auto; }
  .opcao { display: flex; align-items: center; gap: var(--espaco-2); min-height: 32px; }
  input[type='checkbox'] { flex: 0 0 auto; width: 18px; height: 18px; margin: 0; }
  @media (max-width: 560px) { .comparacao { padding: 20px 16px; } }
  .legenda i { display: inline-block; width: 14px; height: 3px; margin-right: 5px; vertical-align: middle; }
  .sumario { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--cor-borda); display: grid; gap: 8px; font-size: var(--texto-xs); }
  .escopo { margin: 4px 0; font-weight: 600; color: var(--cor-verde); }
  .escopo[data-completo='false'] { color: var(--cor-alerta); }
  .sumario .btn { justify-self: start; }
</style>
