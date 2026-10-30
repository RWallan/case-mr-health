<script>
  import EntradaPrevisoes from './EntradaPrevisoes.svelte';
  import ComparacaoSkus from './ComparacaoSkus.svelte';
  import GraficoPrevisao from './GraficoPrevisao.svelte';
  import Changelog from './Changelog.svelte';
  import { rotaDoHash } from './changelog.js';
  import LinksApi from './LinksApi.svelte';
  import Recomendacoes from './Recomendacoes.svelte';
  import Upload from './Upload.svelte';
  import FormularioPrevisao from './FormularioPrevisao.svelte';
  import { campoDoErro, horizontePadrao, montarItem } from './formulario.js';
  const api = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
  const mlflow = import.meta.env.VITE_MLFLOW_URL ?? 'http://localhost:5000';
  const skus = ['item A', 'item B', 'item C', 'item D'];

  let rota = $state(rotaDoHash(location.hash));
  let sku = $state('item A');
  let granularidade = $state('diaria');
  let erroPrevisao = $state(null);
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
  const estadoUpload = $derived(enviando ? 'processando' : atualizacao && !mensagemEnvio ? 'sucesso' : 'ocioso');

  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const fmtData = (valor) => new Intl.DateTimeFormat('pt-BR').format(new Date(`${valor}T12:00:00`));

  async function carregarSerie() {
    erro = '';
    erroPrevisao = null;
    previsao = null;
    carregando = true;
    try {
      const resposta = await fetch(
        `${api}/series/${encodeURIComponent(sku)}/${granularidade}`,
      );
      const corpo = await resposta.json();
      if (!resposta.ok) throw new Error(corpo.mensagem ?? 'Não foi possível carregar o histórico.');
      historico = corpo.pontos;
    } catch (falha) {
      erro = falha.message;
      historico = [];
    } finally {
      carregando = false;
    }
  }

  let ultimoHorizonte = null;

  async function buscar(item) {
    ultimoHorizonte = item.horizonte;
    erro = '';
    erroPrevisao = null;
    previsao = null;
    carregando = true;
    try {
      const resposta = await fetch(`${api}/predicoes`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(item),
      });
      const corpo = await resposta.json();
      if (!resposta.ok) {
        if (campoDoErro(corpo)) erroPrevisao = corpo;
        else erro = corpo.mensagem ?? 'Não foi possível gerar a previsão.';
        return;
      }
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
      corpo.append('pedidos', arquivoPedidos);
      corpo.append('itens', arquivoItens);
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
    // Repete o pedido sobre a série atual, sem data manual (ADR 0013).
    await buscar(montarItem({ sku, granularidade, horizonte: ultimoHorizonte ?? horizontePadrao(granularidade) }));
  }

  // O link de salto muda o foco para o conteúdo, e não só a rolagem (o hash troca a rota).
  function irParaConteudo(evento) {
    evento.preventDefault();
    document.getElementById('conteudo')?.focus();
  }

  $effect(() => {
    sku;
    granularidade;
    carregarSerie();
  });
</script>

<svelte:window onhashchange={() => (rota = rotaDoHash(location.hash))} />

<svelte:head>
  <meta name="description" content="Histórico e previsão da demanda da rede MR. HEALTH." />
</svelte:head>

<div class="shell">
  <a class="pular" href="#conteudo" onclick={irParaConteudo}>Pular para o conteúdo</a>
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

  {#if rota === 'changelog'}
    <Changelog {api} />
  {:else}
  <main id="conteudo" tabindex="-1">
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
        <FormularioPrevisao id="painel" {skus} bind:sku bind:granularidade {carregando} erro={erroPrevisao} onenviar={buscar} />
      </aside>

      <section class="results card" aria-label="Resultado da previsão">
        <div class="results-heading">
          <div class="section-heading">
            <span class="step">02</span>
            <div><h2>Demanda ao longo do tempo</h2><p>{sku} · {granularidade === 'diaria' ? 'Diária' : 'Semanal'} · quantidade na rede</p></div>
          </div>
        </div>

        <GraficoPrevisao {historico} {previsao} {granularidade} {carregando} {erro} />

        <div aria-live="polite">
        {#if previsao}
          <div class="forecast-summary">
            <div><span class="summary-label">PREVISÃO PARA {previsao.periodos.length} PERÍODOS</span><strong>{fmt.format(previsao.periodos.reduce((soma, item) => soma + item.quantidade_prevista, 0))}<small> unidades</small></strong></div>
            <div><span class="summary-label">VALOR ESTIMADO</span><strong>R$ {fmt.format(previsao.periodos.reduce((soma, item) => soma + item.valor_previsto, 0))}</strong></div>
            <div><span class="summary-label">MODELO</span><strong>Versão {previsao.versao_modelo}</strong>{#if previsao.origem_modelo === 'atualizacao'}<small>Reajustada com pedidos novos; sem métrica fora da amostra.</small>{/if}</div>
          </div>
          <p class="interval-note">Os intervalos são apresentados por período e não devem ser somados entre períodos.</p>
        {/if}
        </div>
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
        <Upload id="pedidos" rotulo="Planilha de pedidos (.xlsx)" bind:arquivo={arquivoPedidos} estado={estadoUpload} mensagemSucesso="Pedidos enviados." />
        <Upload id="itens" rotulo="Planilha de itens de pedido (.xlsx)" bind:arquivo={arquivoItens} estado={estadoUpload} mensagemSucesso="Itens enviados." />
        <button class="btn btn-bloco" type="submit" disabled={enviando || !arquivoPedidos || !arquivoItens} aria-busy={enviando}>
          {enviando ? 'Enviando…' : 'Enviar e reajustar'} <span aria-hidden="true">→</span>
        </button>
      </form>
      {#if mensagemEnvio}
        <div class="alerta alerta-erro" role="alert">
          {mensagemEnvio}
          {#if errosEnvio.length}
            <!-- svelte-ignore a11y_no_noninteractive_tabindex (região rolável precisa de foco no teclado) -->
            <div class="tabela-rolagem" role="region" aria-label="Erros do envio" tabindex="0">
              <table class="tabela">
                <thead><tr><th scope="col">Onde</th><th scope="col">Problema</th></tr></thead>
                <tbody>{#each errosEnvio as item}<tr><td>{item.campo}</td><td>{item.mensagem}</td></tr>{/each}</tbody>
              </table>
            </div>
          {/if}
        </div>
      {/if}
      <div aria-live="polite">
      {#if atualizacao}
        <div class="update-status">
          <strong>{rotuloEstado[atualizacao.estado]}</strong>
          <p>{atualizacao.pedidos_novos} pedidos novos · {atualizacao.itens_novos} itens · dados até {fmtData(atualizacao.ultimo_dia)}</p>
          {#if atualizacao.series.length}
            <!-- svelte-ignore a11y_no_noninteractive_tabindex (região rolável precisa de foco no teclado) -->
            <div class="tabela-rolagem" role="region" aria-label="Situação das séries reajustadas" tabindex="0">
            <table class="tabela tabela-larga">
              <thead><tr><th scope="col">Série</th><th scope="col">Situação</th><th scope="col">Versão</th></tr></thead>
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
            </div>
          {/if}
          <p class="interval-note">{atualizacao.aviso}</p>
        </div>
      {/if}
      </div>
    </section>

    <footer><span>MR. HEALTH · Planejamento de demanda</span><span>Previsões da rede · Só o envio de pedidos novos reajusta os modelos</span></footer>
  </main>
  {/if}
</div>
