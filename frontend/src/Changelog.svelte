<script>
  // Changelog legível dentro do app (#46): consome GET /changelog.
  import { prepararVersoes } from './changelog.js';
  let { api } = $props();

  let versoes = $state([]);
  let carregando = $state(true);
  let erro = $state('');

  async function carregar() {
    erro = '';
    carregando = true;
    try {
      const resposta = await fetch(`${api}/changelog`);
      if (!resposta.ok) throw new Error('Não foi possível carregar o changelog.');
      versoes = prepararVersoes(await resposta.json());
    } catch (falha) {
      erro = falha.message;
      versoes = [];
    } finally {
      carregando = false;
    }
  }

  $effect(() => {
    carregar();
  });
</script>

<main id="conteudo" tabindex="-1">
  <section class="card changelog" aria-label="Changelog">
    <div class="section-heading">
      <div><h1 class="titulo-pagina">Changelog</h1><p>Mudanças por versão do projeto.</p></div>
    </div>
    <p><a class="link" href="#/">← Voltar à previsão</a></p>

    {#if carregando}
      <p class="carregando" role="status">Carregando…</p>
    {:else if erro}
      <div class="alerta alerta-erro" role="alert">
        {erro}
        <button type="button" class="btn btn-secundario" onclick={carregar}>Tentar de novo</button>
      </div>
    {:else if !versoes.length}
      <p class="limits-note">Nenhuma versão publicada ainda.</p>
    {:else}
      {#each versoes as versao}
        <article class="changelog-versao">
          <h3>{versao.versao} <small>{versao.data}</small></h3>
          {#each versao.secoes as secao}
            <h4>{secao.tipo}</h4>
            <ul>
              {#each secao.itens as item}
                <li>{item.texto}{#if item.issues} <small>({item.issues})</small>{/if}</li>
              {/each}
            </ul>
          {/each}
        </article>
      {/each}
    {/if}
  </section>
</main>

<style>
  .changelog { padding: var(--espaco-5); }
  .titulo-pagina { font-size: 22px; margin: 2px 0 5px; }
  @media (max-width: 560px) { .changelog { padding: var(--espaco-4); } }
  .changelog-versao { overflow-wrap: anywhere; }
  .changelog-versao { border-top: 1px solid var(--cor-borda); margin-top: var(--espaco-4); padding-top: var(--espaco-3); }
  .changelog-versao h3 small { color: var(--cor-texto-suave); font-size: var(--texto-xs); font-weight: 400; }
  .changelog-versao h4 { color: var(--cor-texto-secundario); font-size: var(--texto-sm); margin: var(--espaco-3) 0 var(--espaco-2); }
  .changelog-versao li small { color: var(--cor-texto-suave); }
</style>
