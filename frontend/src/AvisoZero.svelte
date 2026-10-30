<script>
  // Selo de previsão integralmente zero, com tooltip explicativo (#38, ADR 0013).
  import { explicacaoZero } from './grafico.js';

  let { rotulo, id } = $props();
</script>

<span class="aviso-zero" role="status">
  <span class="texto">{rotulo}</span>
  <button class="info" type="button" aria-label="Por que a previsão é zero?" aria-describedby={id}>i</button>
  <span class="dica" role="tooltip" {id}>{explicacaoZero}</span>
</span>

<style>
  .aviso-zero { position: relative; display: inline-flex; align-items: flex-start; gap: var(--espaco-2); max-width: 100%; padding: 6px 8px 6px 10px; border: 1px solid var(--cor-alerta-borda); border-radius: var(--raio-sm); background: var(--cor-alerta-fundo); color: var(--cor-alerta); font-size: var(--texto-xs); line-height: 1.4; }
  .info { flex: 0 0 auto; width: 20px; height: 20px; border: 1px solid currentColor; border-radius: 50%; background: transparent; color: inherit; font: italic 700 var(--texto-xs) var(--fonte-titulo); line-height: 1; cursor: help; }
  .info:focus-visible { outline: 3px solid var(--cor-foco); outline-offset: 2px; }
  .dica { position: absolute; z-index: 2; top: calc(100% + 6px); left: 0; width: min(320px, 90vw); padding: 10px 12px; border: 1px solid var(--cor-alerta-borda); border-radius: var(--raio-sm); background: var(--cor-superficie); color: var(--cor-texto); box-shadow: var(--sombra-cartao); visibility: hidden; opacity: 0; }
  .aviso-zero:hover .dica, .aviso-zero:focus-within .dica { visibility: visible; opacity: 1; }
</style>
