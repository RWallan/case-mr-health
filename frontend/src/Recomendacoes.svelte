<script>
  // Recomendações por SKU, explicação (LLM ou template) e e-mail de alerta simulado (#23).
  let { api, skus } = $props();

  const rotulos = {
    aumento_significativo: { texto: 'Aumento significativo', sinal: '▲' },
    reducao_significativa: { texto: 'Redução significativa', sinal: '▼' },
    estavel: { texto: 'Estável', sinal: '●' },
    insuficiente: { texto: 'Insuficiente', sinal: '?' },
  };
  const motivos = {
    sem_venda_recente: 'Sem venda nas 4 últimas semanas.',
    variacoes_insuficientes: 'Poucas variações históricas para calcular o limite.',
  };
  const origens = { llm: 'Explicação gerada por LLM', template: 'Explicação por template' };

  const fmtPct = (valor) =>
    valor == null ? '—' : `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1, signDisplay: 'exceptZero' }).format(valor * 100)}%`;
  const fmtLimite = (valor) =>
    valor == null ? '—' : `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(valor * 100)}%`;
  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const fmtData = (valor) => new Intl.DateTimeFormat('pt-BR').format(new Date(`${valor}T12:00:00`));

  let itens = $state([]);
  let erro = $state('');
  let carregando = $state(false);

  let email = $state('');
  let skuAlerta = $state('item A');
  let enviando = $state(false);
  let alerta = $state(null);
  let erroAlerta = $state('');

  async function carregar() {
    erro = '';
    carregando = true;
    try {
      itens = await Promise.all(
        skus.map(async (item) => {
          const resposta = await fetch(`${api}/recomendacoes/${encodeURIComponent(item)}`);
          const corpo = await resposta.json();
          if (!resposta.ok) return { sku: item, erro: corpo.mensagem ?? 'Recomendação indisponível.' };
          return { sku: item, ...corpo };
        }),
      );
    } catch (falha) {
      erro = falha.message;
      itens = [];
    } finally {
      carregando = false;
    }
  }

  async function verAlerta(evento) {
    evento.preventDefault();
    erroAlerta = '';
    alerta = null;
    enviando = true;
    try {
      const resposta = await fetch(`${api}/alertas/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, sku: skuAlerta }),
      });
      const corpo = await resposta.json();
      if (!resposta.ok) throw new Error(corpo.mensagem ?? 'Não foi possível gerar o alerta.');
      alerta = corpo;
    } catch (falha) {
      erroAlerta = falha.message;
    } finally {
      enviando = false;
    }
  }

  $effect(() => {
    carregar();
  });
</script>

<section class="card recomendacoes" aria-label="Recomendações">
  <div class="section-heading">
    <span class="step">04</span>
    <div><h2>Recomendações por SKU</h2><p>Variação da demanda prevista (2 semanas) contra a venda recente (4 semanas), comparada ao Q3 histórico.</p></div>
  </div>

  {#if erro}<div class="error" role="alert">{erro}</div>{/if}
  {#if carregando}<p class="nota">Carregando…</p>{/if}

  <ul class="lista">
    {#each itens as item (item.sku)}
      <li class="item" data-resultado={item.resultado ?? 'erro'}>
        <div class="topo">
          <strong>{item.sku}</strong>
          {#if item.resultado}
            <span class="selo" data-resultado={item.resultado}><span aria-hidden="true">{rotulos[item.resultado].sinal}</span> {rotulos[item.resultado].texto}</span>
          {/if}
        </div>
        {#if item.erro}
          <div class="error" role="alert">{item.erro}</div>
        {:else}
          <dl class="numeros">
            <div><dt>Variação</dt><dd>{fmtPct(item.variacao)}</dd></div>
            <div><dt>Limite (Q3)</dt><dd>{fmtLimite(item.limite_aplicado)}</dd></div>
          </dl>
          {#if item.motivo}<p class="motivo">{motivos[item.motivo] ?? item.motivo}</p>{/if}
          <p class="aviso">Aviso: {item.aviso}</p>
          <p class="explicacao">{item.explicacao.texto}</p>
          <p class="origem" data-origem={item.explicacao.origem}>{origens[item.explicacao.origem] ?? item.explicacao.origem}</p>
        {/if}
      </li>
    {/each}
  </ul>

  <form class="alerta-form" onsubmit={verAlerta}>
    <h3>Ver e-mail de alerta</h3>
    <label for="alerta-sku">SKU</label>
    <select id="alerta-sku" bind:value={skuAlerta}>{#each skus as item}<option value={item}>{item}</option>{/each}</select>
    <label for="alerta-email">E-mail do gestor</label>
    <input id="alerta-email" type="email" required placeholder="gestor@exemplo.com.br" bind:value={email} />
    <button type="submit" disabled={enviando}>{enviando ? 'Gerando…' : 'Ver alerta'}</button>
  </form>

  {#if erroAlerta}<div class="error" role="alert">{erroAlerta}</div>{/if}
  {#if alerta}
    <article class="email" aria-live="polite">
      <p class="simulado" role="status">ENVIO SIMULADO · {alerta.aviso_envio}</p>
      <p><strong>Para:</strong> {alerta.destinatario}</p>
      <p><strong>Assunto:</strong> {alerta.assunto}</p>
      <p class="selo" data-resultado={alerta.recomendacao.resultado}><span aria-hidden="true">{rotulos[alerta.recomendacao.resultado].sinal}</span> {rotulos[alerta.recomendacao.resultado].texto}</p>
      <p>{alerta.recomendacao.texto}</p>
      <p>Variação {fmtPct(alerta.recomendacao.variacao)} · Q3 {fmtLimite(alerta.recomendacao.limite_aplicado)}</p>
      <table class="erros">
        <thead><tr><th>Semana</th><th>Demanda</th><th>Intervalo 80%</th><th>Intervalo 95%</th><th>Valor (R$)</th></tr></thead>
        <tbody>
          {#each alerta.periodos as periodo}
            <tr>
              <td>{fmtData(periodo.data_alvo)}</td>
              <td>{fmt.format(periodo.quantidade_prevista)}</td>
              <td>{periodo.limite_inferior_80 == null ? '—' : `${fmt.format(periodo.limite_inferior_80)} a ${fmt.format(periodo.limite_superior_80)}`}</td>
              <td>{periodo.limite_inferior_95 == null ? '—' : `${fmt.format(periodo.limite_inferior_95)} a ${fmt.format(periodo.limite_superior_95)}`}</td>
              <td>{fmt.format(periodo.valor_previsto)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      <p>Valor total previsto: R$ {fmt.format(alerta.valor_total_previsto)}</p>
      <p class="aviso">Aviso: {alerta.recomendacao.aviso}</p>
    </article>
  {/if}
</section>

<style>
  .recomendacoes { margin-top: 24px; padding: 24px 25px; }
  .nota { color: #74837d; font-size: 12px; }
  .lista { list-style: none; padding: 0; margin: 18px 0 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
  .item { border: 1px solid #e6ebe6; border-left-width: 5px; border-radius: 10px; padding: 14px; font-size: 12px; }
  .item[data-resultado='aumento_significativo'] { border-left-color: #c0572b; background: #fff7f2; }
  .item[data-resultado='reducao_significativa'] { border-left-color: #3d6f8e; background: #f3f8fb; }
  .item[data-resultado='estavel'] { border-left-color: #739354; background: #f7faf3; }
  .item[data-resultado='insuficiente'] { border-left-color: #8a9891; border-left-style: dashed; background: #f6f7f6; }
  .topo { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  .selo { display: inline-block; font-weight: 700; font-size: 11px; padding: 3px 8px; border-radius: 999px; border: 1px solid currentColor; }
  .selo[data-resultado='aumento_significativo'] { color: #9c3f17; }
  .selo[data-resultado='reducao_significativa'] { color: #2b5873; }
  .selo[data-resultado='estavel'] { color: #4d6b33; }
  .selo[data-resultado='insuficiente'] { color: #5b6b64; }
  .numeros { display: flex; gap: 22px; margin: 12px 0 6px; }
  .numeros div { display: grid; gap: 2px; }
  dt { color: #87958e; font-size: 10px; font-weight: 700; letter-spacing: .08em; }
  dd { margin: 0; font-size: 16px; font-weight: 700; font-family: Manrope, sans-serif; }
  .motivo, .aviso { color: #9a5f1f; margin: 4px 0; }
  .explicacao { margin: 8px 0 4px; line-height: 1.5; }
  .origem { margin: 0; font-size: 10px; color: #74837d; font-weight: 600; }
  .alerta-form { margin-top: 22px; padding-top: 16px; border-top: 1px solid #e6ebe6; display: grid; gap: 6px; max-width: 32rem; font-size: 12px; }
  .alerta-form h3 { font-size: 14px; margin-bottom: 4px; }
  .alerta-form input, .alerta-form select { height: 38px; border: 1px solid #dfe6df; border-radius: 8px; padding: 0 12px; }
  button { justify-self: start; height: 38px; margin-top: 6px; padding: 0 16px; border: 0; border-radius: 8px; background: #234d3e; color: #fff; font-weight: 600; font-size: 12px; cursor: pointer; }
  button:disabled { opacity: .55; cursor: wait; }
  .email { margin-top: 16px; border: 1px solid #dfe6df; border-radius: 10px; padding: 16px; font-size: 12px; max-width: 46rem; }
  .email p { margin: 6px 0; }
  .simulado { background: #fff3d6; color: #6b4a0b; font-weight: 700; padding: 8px 10px; border-radius: 8px; border: 1px solid #e3c277; }
</style>
