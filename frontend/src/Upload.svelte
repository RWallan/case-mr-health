<script>
  // Upload reutilizável de planilha .xlsx (#43): arrastar e soltar, clique ou
  // teclado, nome e tamanho, trocar/remover, validação no cliente. Sem barra
  // de progresso em bytes: o processamento vem do estado do pai.
  import { EXTENSAO, formatarTamanho, primeiroArquivo, validarArquivo } from './upload.js';

  // estado: 'ocioso' | 'processando' | 'sucesso'
  let { id, rotulo, arquivo = $bindable(null), estado = 'ocioso', mensagemSucesso = 'Enviado.' } = $props();

  let entrada;
  let arrastando = $state(false);
  let erro = $state('');

  const bloqueado = $derived(estado === 'processando');

  function escolher(novo) {
    if (!novo) return;
    erro = validarArquivo(novo);
    if (erro) return;
    arquivo = novo;
  }

  function aoSelecionar(event) {
    escolher(primeiroArquivo(event.currentTarget.files));
    event.currentTarget.value = '';
  }

  function aoSoltar(event) {
    event.preventDefault();
    arrastando = false;
    if (!bloqueado) escolher(primeiroArquivo(event.dataTransfer?.files));
  }

  function abrir() {
    if (!bloqueado) entrada.click();
  }

  function aoTeclar(event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      abrir();
    }
  }

  function remover() {
    arquivo = null;
    erro = '';
  }
</script>

<div class="upload">
  <span class="rotulo" id={`${id}-rotulo`}>{rotulo}</span>
  <div
    class="zona"
    class:arrastando
    class:invalido={!!erro}
    class:sucesso={estado === 'sucesso'}
    role="button"
    tabindex={bloqueado ? -1 : 0}
    aria-labelledby={`${id}-rotulo`}
    aria-describedby={`${id}-ajuda ${id}-status`}
    aria-disabled={bloqueado}
    aria-busy={bloqueado}
    onclick={abrir}
    onkeydown={aoTeclar}
    ondragover={(e) => { e.preventDefault(); if (!bloqueado) arrastando = true; }}
    ondragleave={() => (arrastando = false)}
    ondrop={aoSoltar}
  >
    {#if arquivo}
      <span class="nome">{arquivo.name}</span>
      <span class="tamanho">{formatarTamanho(arquivo.size)}</span>
    {:else}
      <span class="chamada">Arraste a planilha aqui ou <span class="link">escolha um arquivo</span></span>
    {/if}
    <input {id} class="oculto" type="file" accept={EXTENSAO} tabindex="-1" aria-hidden="true" bind:this={entrada} onchange={aoSelecionar} />
  </div>
  <p class="ajuda" id={`${id}-ajuda`}>Somente {EXTENSAO}, até 5 MB.</p>
  <div class="status" id={`${id}-status`} aria-live="polite">
    {#if erro}
      <span class="msg-erro">{erro}</span>
    {:else if estado === 'processando'}
      <span class="carregando">Processando…</span>
    {:else if estado === 'sucesso'}
      <span class="msg-sucesso">{mensagemSucesso}</span>
    {/if}
  </div>
  {#if arquivo}
    <div class="acoes">
      <button class="btn btn-secundario" type="button" onclick={abrir} disabled={bloqueado}>Trocar</button>
      <button class="btn btn-secundario" type="button" onclick={remover} disabled={bloqueado}>Remover</button>
    </div>
  {/if}
</div>

<style>
  .upload { display: block; }
  .zona { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: var(--espaco-2) var(--espaco-3); min-height: 72px; padding: var(--espaco-4); border: 2px dashed var(--cor-borda-campo); border-radius: var(--raio-sm); background: var(--cor-superficie); color: var(--cor-texto-secundario); font-size: var(--texto-sm); text-align: center; cursor: pointer; }
  .zona:hover { border-color: var(--cor-verde-link); background: var(--cor-lima-suave); }
  .zona:focus-visible { outline: 3px solid var(--cor-foco); outline-offset: 2px; border-color: var(--cor-foco); }
  .zona.arrastando { border-style: solid; border-color: var(--cor-foco); background: var(--cor-lima-suave); }
  .zona.invalido { border-color: var(--cor-erro); background: var(--cor-erro-fundo); }
  .zona.sucesso { border-color: var(--cor-sucesso); background: var(--cor-sucesso-fundo); }
  .zona[aria-disabled='true'] { cursor: wait; opacity: .7; }
  .link { color: var(--cor-verde-link); font-weight: 600; text-decoration: underline; }
  .nome { color: var(--cor-texto-forte); font-weight: 600; overflow-wrap: anywhere; }
  .tamanho { color: var(--cor-texto-suave); font-size: var(--texto-xs); }
  .oculto { display: none; }
  .ajuda { margin: var(--espaco-2) 0 0; color: var(--cor-texto-suave); font-size: var(--texto-xs); }
  .status { min-height: 1.25em; margin-top: var(--espaco-2); font-size: var(--texto-xs); }
  .msg-erro { color: var(--cor-erro); font-weight: 600; }
  .msg-sucesso { color: var(--cor-sucesso); font-weight: 600; }
  .acoes { display: flex; gap: var(--espaco-2); margin-top: var(--espaco-2); }
  .acoes .btn { height: 34px; }
  @media (prefers-reduced-motion: no-preference) { .zona { transition: border-color .15s, background .15s; } }
</style>
