<script>
  import {
    campoDoErro,
    horizontePadrao,
    limiteDe,
    mensagemDoErro,
    montarItem,
    validarHorizonte,
  } from './formulario.js';

  // Formulário único de pedido de previsão (#41): SKU, granularidade e períodos
  // a prever. A data de referência manual fica em "Avançado" (ADR 0013).
  // `erro` é o corpo de erro da API ({codigo, mensagem, campo}) ou null.
  let {
    id,
    skus,
    sku = $bindable('item A'),
    granularidade = $bindable('diaria'),
    carregando = false,
    erro = null,
    rotuloEnvio = 'Gerar previsão',
    onenviar,
  } = $props();

  const granularidades = [
    { valor: 'diaria', rotulo: 'Diária' },
    { valor: 'semanal', rotulo: 'Semanal' },
  ];

  let horizonte = $state(horizontePadrao(granularidade));
  let dataManual = $state('');
  let tentou = $state(false);

  const limite = $derived(limiteDe(granularidade));
  const erroHorizonteLocal = $derived(validarHorizonte(horizonte, granularidade));
  const campoApi = $derived(erro ? campoDoErro(erro) : '');
  const mensagemApi = $derived(erro ? mensagemDoErro(erro, granularidade) : '');
  const erroHorizonte = $derived(
    tentou && erroHorizonteLocal ? erroHorizonteLocal : campoApi === 'horizonte' ? mensagemApi : '',
  );
  const erroData = $derived(campoApi === 'data_referencia' ? mensagemApi : '');
  const erroGeral = $derived(erro && !['horizonte', 'data_referencia'].includes(campoApi) ? mensagemApi : '');
  // "Avançado" abre sozinho quando a data manual causou o erro.
  const avancadoAberto = $derived(Boolean(dataManual) || Boolean(erroData));

  function escolher(valor) {
    if (valor === granularidade) return;
    granularidade = valor;
    horizonte = horizontePadrao(valor);
    tentou = false;
  }

  function enviar(event) {
    event.preventDefault();
    tentou = true;
    if (erroHorizonteLocal) return;
    onenviar(montarItem({ sku, granularidade, horizonte, dataManual }));
  }
</script>

<form class="formulario-previsao" onsubmit={enviar} novalidate>
  <label class="rotulo" for={`${id}-sku`}>SKU</label>
  <select id={`${id}-sku`} class="campo" bind:value={sku}>
    {#each skus as opcao}<option value={opcao}>{opcao}</option>{/each}
  </select>

  <span class="rotulo" id={`${id}-granularidade`}>Granularidade</span>
  <div class="segmented" role="group" aria-labelledby={`${id}-granularidade`}>
    {#each granularidades as opcao}
      <button type="button" class:active={granularidade === opcao.valor} aria-pressed={granularidade === opcao.valor} onclick={() => escolher(opcao.valor)}>{opcao.rotulo}</button>
    {/each}
  </div>

  <label class="rotulo" for={`${id}-horizonte`}>Períodos a prever (1 a {limite.maximo})</label>
  <input
    id={`${id}-horizonte`}
    class="campo"
    type="number"
    min="1"
    max={limite.maximo}
    step="1"
    bind:value={horizonte}
    aria-invalid={erroHorizonte ? 'true' : undefined}
    aria-describedby={erroHorizonte ? `${id}-horizonte-erro` : undefined}
  />
  {#if erroHorizonte}<p class="erro-campo" id={`${id}-horizonte-erro`} role="alert">{erroHorizonte}</p>{/if}

  <details class="avancado" open={avancadoAberto}>
    <summary>Avançado</summary>
    <label class="rotulo" for={`${id}-data`}>Data de referência (opcional)</label>
    <input
      id={`${id}-data`}
      class="campo"
      type="date"
      bind:value={dataManual}
      aria-invalid={erroData ? 'true' : undefined}
      aria-describedby={`${id}-data-ajuda${erroData ? ` ${id}-data-erro` : ''}`}
    />
    {#if erroData}<p class="erro-campo" id={`${id}-data-erro`} role="alert">{erroData}</p>{/if}
    <p class="limits-note" id={`${id}-data-ajuda`}>
      Vazia, a previsão parte do fim do treino do modelo, que coincide com o último período histórico. Informada, ela
      precisa ser a última data conhecida: o passo até o fim do treino somado aos períodos pedidos não pode passar de
      {limite.maximo} {limite.unidade}.
    </p>
  </details>

  {#if erroGeral}<p class="erro-campo" role="alert">{erroGeral}</p>{/if}

  <button class="btn btn-bloco" type="submit" disabled={carregando} aria-busy={carregando}>
    {carregando ? 'Carregando…' : rotuloEnvio} <span aria-hidden="true">→</span>
  </button>
  <p class="limits-note">Limite validado: {limite.maximo} {limite.unidade} após o fim do treino.</p>
</form>
