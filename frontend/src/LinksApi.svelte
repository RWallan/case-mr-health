<script>
  // Links de documentação da API ao lado do link do MLflow (#25).
  let { api } = $props();
  const docs = import.meta.env.VITE_DOCS_URL ?? 'http://localhost:8001';
</script>

<a class="link" href={`${api}/docs`} target="_blank" rel="noreferrer">Swagger <span aria-hidden="true">↗</span></a>
<a class="link" href="#/changelog">Changelog</a>
<a class="link" href={docs} target="_blank" rel="noreferrer">Documentação <span aria-hidden="true">↗</span></a>

