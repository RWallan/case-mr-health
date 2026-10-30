<script>
  // Gráfico do histórico e da previsão, com eixo por data (#38).
  import AvisoZero from './AvisoZero.svelte';
  import { escalas, JANELA_RECENTE, marcasDoEixo, montarSerie, pontoMaisProximo, textoZero } from './grafico.js';

  let { historico, previsao, granularidade, carregando = false, erro = '' } = $props();

  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const fmtData = new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC' });
  const fmtCurta = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', timeZone: 'UTC' });
  const margem = { esquerda: 44, direita: 16, topo: 16, base: 34 };

  let janela = $state('recente');
  let largura = $state(900);
  let ativo = $state(null);

  let altura = $derived(largura < 480 ? 240 : 300);
  let serie = $derived(montarSerie({ historico, previsao, granularidade, janela }));
  let escala = $derived(escalas({ largura, altura, margem, dominio: serie.dominio, teto: serie.teto }));
  let marcas = $derived(marcasDoEixo(serie.dominio, largura < 480 ? 3 : 5));
  let temIntervalo = $derived(serie.previsao.some((p) => p.intervalo80 || p.intervalo95));
  let linhaHistorico = $derived(serie.historico.map((p) => `${escala.x(p.ms)},${escala.y(p.valor)}`).join(' '));
  let linhaPrevisao = $derived(serie.previsao.map((p) => `${escala.x(p.ms)},${escala.y(p.valor)}`).join(' '));
  let rotuloInicioADireita = $derived(serie.inicioPrevisao !== null && escala.x(serie.inicioPrevisao) > largura - 130);
  let unidade = $derived(granularidade === 'diaria' ? 'dias' : 'semanas');

  function aoMover(evento) {
    const caixa = evento.currentTarget.getBoundingClientRect();
    const [minimo, maximo] = serie.dominio;
    const util = largura - margem.esquerda - margem.direita;
    const ms = minimo + ((evento.clientX - caixa.left - margem.esquerda) / util) * (maximo - minimo);
    ativo = pontoMaisProximo(serie, ms);
  }

  const descricao = (ponto) => `${ponto.tipo === 'previsao' ? 'Previsão' : 'Histórico'} em ${fmtData.format(ponto.ms)}: ${fmt.format(ponto.valor)} unidades`;
</script>

<div class="grafico">
  {#if erro}<div class="alerta alerta-erro" role="alert">{erro}</div>{/if}

  {#if carregando && serie.vazio}
    <div class="empty-state" role="status"><span class="carregando">Carregando o histórico…</span></div>
  {:else if serie.vazio}
    <div class="empty-state"><div class="empty-icon" aria-hidden="true">⌁</div><h3>Sem dados para esta série</h3><p>O gráfico mostra as vendas até o último período disponível e a previsão gerada.</p></div>
  {:else}
    <div class="barra">
      <div class="legend" aria-label="Legenda">
        <span><i class="traco historico"></i> Histórico</span>
        <span><i class="traco previsao"></i> Previsão</span>
        {#if temIntervalo}<span><i class="traco i95"></i> Intervalo 80% / 95%</span>{/if}
      </div>
      <div class="segmented janela" role="group" aria-label="Janela do histórico">
        <button type="button" class:active={janela === 'recente'} aria-pressed={janela === 'recente'} onclick={() => (janela = 'recente')}>Recente</button>
        <button type="button" class:active={janela === 'completo'} aria-pressed={janela === 'completo'} onclick={() => (janela = 'completo')}>Completo</button>
      </div>
    </div>

    <div class="chart-wrap" bind:clientWidth={largura}>
      <svg width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={`Gráfico do histórico e da previsão de vendas${serie.zero ? ' (previsão toda zero)' : ''}`}>
        {#if serie.inicioPrevisao !== null && serie.fimPrevisao !== null}
          <rect x={escala.x(serie.inicioPrevisao)} y={margem.topo} width={Math.max(0, escala.x(serie.fimPrevisao) - escala.x(serie.inicioPrevisao))} height={altura - margem.topo - margem.base} class="faixa-previsao" />
        {/if}
        {#each [0, serie.maximo / 2, serie.maximo] as valor}
          <line x1={margem.esquerda} y1={escala.y(valor)} x2={largura - margem.direita} y2={escala.y(valor)} class={valor === 0 ? 'axis' : 'gridline'} />
          <text x={margem.esquerda - 8} y={escala.y(valor) + 4} class="tick" text-anchor="end">{fmt.format(valor)}</text>
        {/each}
        {#each marcas as ms, indice}
          <text x={escala.x(ms)} y={altura - 10} class="tick" text-anchor={indice === 0 ? 'start' : indice === marcas.length - 1 ? 'end' : 'middle'}>{fmtCurta.format(ms)}</text>
        {/each}

        {#if serie.historico.length > 1}<polyline points={linhaHistorico} class="history-line" />{/if}
        {#if serie.historico.length === 1}<circle cx={escala.x(serie.historico[0].ms)} cy={escala.y(serie.historico[0].valor)} r="3" class="history-dot" />{/if}

        {#if serie.inicioPrevisao !== null}
          <line x1={escala.x(serie.inicioPrevisao)} y1={margem.topo} x2={escala.x(serie.inicioPrevisao)} y2={altura - margem.base} class="split-line" />
          <text x={escala.x(serie.inicioPrevisao) + (rotuloInicioADireita ? -6 : 6)} y={margem.topo + 12} class="rotulo-inicio" text-anchor={rotuloInicioADireita ? 'end' : 'start'}>Início da previsão · {fmtData.format(serie.inicioPrevisao)}</text>
        {/if}

        {#each serie.previsao as ponto}
          {#if ponto.intervalo95}<line x1={escala.x(ponto.ms)} y1={escala.y(ponto.intervalo95.superior)} x2={escala.x(ponto.ms)} y2={escala.y(ponto.intervalo95.inferior)} class="interval-95" />{/if}
          {#if ponto.intervalo80}<line x1={escala.x(ponto.ms)} y1={escala.y(ponto.intervalo80.superior)} x2={escala.x(ponto.ms)} y2={escala.y(ponto.intervalo80.inferior)} class="interval-80" />{/if}
        {/each}
        {#if serie.previsao.length > 1}<polyline points={linhaPrevisao} class="forecast-line" />{/if}
        {#each serie.previsao as ponto}
          <circle cx={escala.x(ponto.ms)} cy={escala.y(ponto.valor)} r="5" class="forecast-point" tabindex="0" role="img" aria-label={descricao({ ...ponto, tipo: 'previsao' })} onfocus={() => (ativo = { ...ponto, tipo: 'previsao' })} onblur={() => (ativo = null)} />
        {/each}

        {#if ativo}
          <line x1={escala.x(ativo.ms)} y1={margem.topo} x2={escala.x(ativo.ms)} y2={altura - margem.base} class="guia" />
          <circle cx={escala.x(ativo.ms)} cy={escala.y(ativo.valor)} r="6" class="ponto-ativo" />
        {/if}
        <rect x={margem.esquerda} y={margem.topo} width={Math.max(0, largura - margem.esquerda - margem.direita)} height={altura - margem.topo - margem.base} fill="none" pointer-events="all" role="presentation" onpointermove={aoMover} onpointerleave={() => (ativo = null)} />
      </svg>

      {#if ativo}
        <div class="tooltip" style:left={`${Math.min(Math.max(escala.x(ativo.ms), 90), largura - 90)}px`} style:top={`${margem.topo}px`} aria-hidden="true">
          <strong>{ativo.tipo === 'previsao' ? 'Previsão' : 'Histórico'} · {fmtData.format(ativo.ms)}</strong>
          <span>{fmt.format(ativo.valor)} unidades</span>
          {#if ativo.intervalo80}<span>80%: {fmt.format(ativo.intervalo80.inferior)} a {fmt.format(ativo.intervalo80.superior)}</span>{/if}
          {#if ativo.intervalo95}<span>95%: {fmt.format(ativo.intervalo95.inferior)} a {fmt.format(ativo.intervalo95.superior)}</span>{/if}
        </div>
      {/if}

      {#if serie.zero}
        <div class="area-zero" style:left={`${margem.esquerda + 8}px`} style:top={`${margem.topo + 24}px`}>
          <AvisoZero rotulo={textoZero} id="dica-zero-grafico" />
        </div>
      {/if}
    </div>

    <p class="chart-footnote">
      {#if serie.recortado}Histórico recente (últimos {JANELA_RECENTE[granularidade]} {unidade} antes da previsão); use "Completo" para ver toda a série.{/if}
      {#if serie.inicioPrevisao !== null}A previsão começa depois da linha "Início da previsão".{/if}
      {#if temIntervalo}A faixa externa é o intervalo de 95%.{/if}
    </p>
  {/if}
</div>

<style>
  .grafico { margin-top: 24px; }
  .barra { display: flex; justify-content: space-between; align-items: center; gap: var(--espaco-3); flex-wrap: wrap; }
  .legend { flex-wrap: wrap; padding-top: 0; white-space: normal; gap: var(--espaco-4); }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .traco { display: inline-block; width: 22px; height: 0; border-top: 3px solid; }
  .traco.historico { border-color: var(--cor-historico); }
  .traco.previsao { border-color: var(--cor-previsao); border-top-style: dashed; }
  .traco.i95 { border-color: var(--cor-intervalo-95); border-top-width: 8px; border-radius: 4px; }
  .janela { width: 180px; }
  .chart-wrap { position: relative; margin-top: var(--espaco-3); }
  svg { display: block; overflow: visible; }
  .faixa-previsao { fill: var(--cor-previsao); opacity: .12; }
  .history-dot { fill: var(--cor-historico); }
  .rotulo-inicio { fill: var(--cor-previsao-texto); font-size: var(--texto-xs); font-weight: 700; }
  .guia { stroke: var(--cor-divisao); stroke-width: 1; }
  .ponto-ativo { fill: none; stroke: var(--cor-texto); stroke-width: 2; }
  .forecast-point:focus-visible { outline: 3px solid var(--cor-foco); outline-offset: 2px; }
  .tooltip { position: absolute; z-index: 1; transform: translateX(-50%); display: grid; gap: 2px; padding: 8px 10px; border: 1px solid var(--cor-borda-campo); border-radius: var(--raio-sm); background: var(--cor-superficie); box-shadow: var(--sombra-cartao); font-size: var(--texto-xs); white-space: nowrap; pointer-events: none; }
  .area-zero { position: absolute; max-width: calc(100% - 70px); }
  .chart-footnote { margin-left: 0; }
</style>
