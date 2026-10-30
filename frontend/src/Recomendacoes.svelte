<script>
  // Recomendações por SKU, explicação (LLM ou template) e e-mail de alerta simulado (#23).
  import { PROVEDORES, montarModelo, modeloValido, cabecalhosLlm, avisoTemplate } from './llm.js';
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

  // A chave fica só na memória desta página: não vai para o armazenamento do navegador.
  let provedor = $state('openai');
  let modeloLlm = $state('');
  let chaveLlm = $state('');
  let mostrarChave = $state(false);

  const provedorAtual = $derived(PROVEDORES.find((p) => p.id === provedor));
  const modeloComposto = $derived(montarModelo(provedor, modeloLlm));
  const modeloInvalido = $derived(!!chaveLlm && !modeloValido(modeloComposto));

  let itens = $state([]);
  let erro = $state('');
  let carregando = $state(false);

  let email = $state('');
  let skuAlerta = $state('item A');
  let enviando = $state(false);
  let alerta = $state(null);
  let erroAlerta = $state('');

  async function carregarSku(item, cabecalhos) {
    try {
      const resposta = await fetch(`${api}/recomendacoes/${encodeURIComponent(item)}`, { headers: cabecalhos });
      const corpo = await resposta.json();
      if (!resposta.ok) return { sku: item, erro: corpo.mensagem ?? 'Recomendação indisponível.' };
      return { sku: item, usouLlm: 'X-LLM-Chave' in cabecalhos, ...corpo };
    } catch (falha) {
      return { sku: item, erro: falha.message };
    }
  }

  async function carregar() {
    erro = '';
    carregando = true;
    const cabecalhos = cabecalhosLlm(provedor, modeloLlm, chaveLlm);
    itens = skus.map((item) => ({ sku: item, processando: true }));
    await Promise.all(
      skus.map(async (item, i) => {
        const pronto = await carregarSku(item, cabecalhos);
        itens[i] = pronto;
      }),
    );
    carregando = false;
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
    <span class="step">05</span>
    <div><h2>Recomendações por SKU</h2><p>Variação da demanda prevista (2 semanas) contra a venda recente (4 semanas), comparada ao Q3 histórico.</p></div>
  </div>

  <form class="llm-form" onsubmit={(evento) => { evento.preventDefault(); carregar(); }}>
    <h3>LLM da explicação (opcional)</h3>
    <p class="nota">Informe o modelo (formato <code>provedor/modelo</code>) e a sua chave de API. Funciona com OpenAI, Anthropic, Gemini e outros. A chave é enviada só nas consultas desta página, não é armazenada e não aparece em log. Sem chave, a explicação vem do template.</p>
    <label class="rotulo" for="llm-provedor">Provedor</label>
    <select id="llm-provedor" class="campo" bind:value={provedor}>{#each PROVEDORES as p}<option value={p.id}>{p.rotulo}</option>{/each}</select>
    <label class="rotulo" for="llm-modelo">Modelo{provedor === 'outro' ? ' (provedor/modelo)' : ''}</label>
    <input id="llm-modelo" class="campo" bind:value={modeloLlm} placeholder={provedorAtual.exemplo} aria-invalid={modeloInvalido} aria-describedby="llm-modelo-ajuda" autocomplete="off" />
    <p id="llm-modelo-ajuda" class="nota">Enviado como <code>{modeloComposto || 'provedor/modelo'}</code>.{#if modeloInvalido} <span class="erro-campo" role="alert">Informe o modelo no formato provedor/modelo; sem ele a chave não é enviada.</span>{/if}</p>
    <label class="rotulo" for="llm-chave">Chave de API</label>
    <div class="chave">
      <input id="llm-chave" class="campo" type={mostrarChave ? 'text' : 'password'} bind:value={chaveLlm} autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="sk-…" />
      <button class="btn btn-secundario" type="button" aria-pressed={mostrarChave} onclick={() => (mostrarChave = !mostrarChave)}>Mostrar chave</button>
    </div>
    <button class="btn btn-secundario" type="submit" disabled={carregando} aria-busy={carregando}>{carregando ? 'Carregando…' : 'Aplicar e recarregar'}</button>
  </form>

  {#if erro}<div class="alerta alerta-erro" role="alert">{erro}</div>{/if}

  <ul class="lista">
    {#each itens as item (item.sku)}
      <li class="item" data-resultado={item.resultado ?? 'erro'}>
        <div class="topo">
          <strong>{item.sku}</strong>
          {#if item.resultado}
            <span class="selo" data-resultado={item.resultado}><span aria-hidden="true">{rotulos[item.resultado].sinal}</span> {rotulos[item.resultado].texto}</span>
          {/if}
        </div>
        {#if item.processando}
          <p class="carregando" role="status">Processando…</p>
        {:else if item.erro}
          <div class="alerta alerta-erro" role="alert">{item.erro}</div>
        {:else}
          <dl class="numeros">
            <div><dt>Variação</dt><dd>{fmtPct(item.variacao)}</dd></div>
            <div><dt>Limite (Q3)</dt><dd>{fmtLimite(item.limite_aplicado)}</dd></div>
          </dl>
          {#if item.motivo}<p class="motivo">{motivos[item.motivo] ?? item.motivo}</p>{/if}
          <p class="aviso">Aviso: {item.aviso}</p>
          <p class="explicacao">{item.explicacao.texto}</p>
          <p class="origem" data-origem={item.explicacao.origem}>{origens[item.explicacao.origem] ?? item.explicacao.origem}</p>
          {#if avisoTemplate(item.explicacao.origem, item.usouLlm)}<p class="motivo" role="status">{avisoTemplate(item.explicacao.origem, item.usouLlm)}</p>{/if}
        {/if}
      </li>
    {/each}
  </ul>

  <form class="alerta-form" onsubmit={verAlerta}>
    <h3>Ver e-mail de alerta</h3>
    <label class="rotulo" for="alerta-sku">SKU</label>
    <select id="alerta-sku" class="campo" bind:value={skuAlerta}>{#each skus as item}<option value={item}>{item}</option>{/each}</select>
    <label class="rotulo" for="alerta-email">E-mail do gestor</label>
    <input id="alerta-email" class="campo" type="email" required placeholder="gestor@exemplo.com.br" bind:value={email} />
    <button class="btn btn-secundario" type="submit" disabled={enviando} aria-busy={enviando}>{enviando ? 'Gerando…' : 'Ver alerta'}</button>
  </form>

  {#if erroAlerta}<div class="alerta alerta-erro" role="alert">{erroAlerta}</div>{/if}
  <div aria-live="polite">
  {#if alerta}
    <article class="email">
      <p class="simulado" role="status">ENVIO SIMULADO · {alerta.aviso_envio}</p>
      <p><strong>Para:</strong> {alerta.destinatario}</p>
      <p><strong>Assunto:</strong> {alerta.assunto}</p>
      <p class="selo" data-resultado={alerta.recomendacao.resultado}><span aria-hidden="true">{rotulos[alerta.recomendacao.resultado].sinal}</span> {rotulos[alerta.recomendacao.resultado].texto}</p>
      <p>{alerta.recomendacao.texto}</p>
      <p>Variação {fmtPct(alerta.recomendacao.variacao)} · Q3 {fmtLimite(alerta.recomendacao.limite_aplicado)}</p>
      <!-- svelte-ignore a11y_no_noninteractive_tabindex (região rolável precisa de foco no teclado) -->
      <div class="tabela-rolagem" role="region" aria-label="Previsão por semana" tabindex="0">
      <table class="tabela tabela-larga">
        <thead><tr><th scope="col">Semana</th><th scope="col">Demanda</th><th scope="col">Intervalo 80%</th><th scope="col">Intervalo 95%</th><th scope="col">Valor (R$)</th></tr></thead>
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
      </div>
      <p>Valor total previsto: R$ {fmt.format(alerta.valor_total_previsto)}</p>
      <p class="aviso">Aviso: {alerta.recomendacao.aviso}</p>
    </article>
  {/if}
  </div>
</section>

<style>
  .recomendacoes { margin-top: 24px; padding: 24px 25px; }
  .nota { color: var(--cor-texto-suave); font-size: var(--texto-xs); overflow-wrap: anywhere; }
  .lista { list-style: none; padding: 0; margin: 18px 0 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr)); gap: 14px; }
  .item { border: 1px solid var(--cor-borda); border-left-width: 5px; border-radius: 10px; padding: 14px; font-size: var(--texto-xs); }
  .item[data-resultado='aumento_significativo'] { border-left-color: var(--cor-aumento); background: var(--cor-aumento-fundo); }
  .item[data-resultado='reducao_significativa'] { border-left-color: var(--cor-info); background: var(--cor-info-fundo); }
  .item[data-resultado='estavel'] { border-left-color: var(--cor-historico); background: var(--cor-sucesso-fundo); }
  .item[data-resultado='insuficiente'] { border-left-color: var(--cor-texto-suave); border-left-style: dashed; background: var(--cor-neutro-fundo); }
  .topo { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  .selo { display: inline-block; font-weight: 700; font-size: var(--texto-xs); padding: 3px 8px; border-radius: var(--raio-pilula); border: 1px solid currentColor; }
  .selo[data-resultado='aumento_significativo'] { color: var(--cor-aumento); }
  .selo[data-resultado='reducao_significativa'] { color: var(--cor-info); }
  .selo[data-resultado='estavel'] { color: var(--cor-sucesso); }
  .selo[data-resultado='insuficiente'] { color: var(--cor-texto-secundario); }
  .numeros { display: flex; gap: 22px; margin: 12px 0 6px; }
  .numeros div { display: grid; gap: 2px; }
  dt { color: var(--cor-texto-suave); font-size: var(--texto-xs); font-weight: 700; letter-spacing: .08em; }
  dd { margin: 0; font-size: 16px; font-weight: 700; font-family: var(--fonte-titulo); }
  .motivo, .aviso { color: var(--cor-alerta); margin: 4px 0; }
  .explicacao { margin: 8px 0 4px; line-height: 1.5; }
  .origem { margin: 0; font-size: var(--texto-xs); color: var(--cor-texto-suave); font-weight: 600; }
  .llm-form { margin-top: 16px; display: grid; gap: 6px; max-width: 32rem; font-size: var(--texto-xs); }
  .llm-form h3 { font-size: 14px; margin-bottom: 0; }
  .chave { display: flex; gap: var(--espaco-2); }
  .chave .campo { flex: 1; min-width: 0; }
  .chave .btn { flex: 0 0 auto; }
  .erro-campo { color: var(--cor-erro); font-weight: 600; }
  .alerta-form { margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--cor-borda); display: grid; gap: 6px; max-width: 32rem; font-size: var(--texto-xs); }
  .alerta-form h3 { font-size: 14px; margin-bottom: 4px; }
  .llm-form .btn, .alerta-form .btn { justify-self: start; margin-top: 6px; }
  .email { margin-top: 16px; border: 1px solid var(--cor-borda-campo); border-radius: 10px; padding: 16px; font-size: var(--texto-xs); max-width: 46rem; }
  .email p { margin: 6px 0; overflow-wrap: anywhere; }
  @media (max-width: 560px) { .recomendacoes { padding: 20px 16px; } .numeros { gap: 16px; } }
  .simulado { background: var(--cor-alerta-fundo); color: var(--cor-alerta); font-weight: 700; padding: 8px 10px; border-radius: var(--raio-sm); border: 1px solid var(--cor-alerta-borda); }
</style>
