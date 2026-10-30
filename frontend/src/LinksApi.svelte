<script>
  // Links de documentação da API ao lado do link do MLflow (#25).
  let { api } = $props();
</script>

<a class="api-link" href={`${api}/docs`} target="_blank" rel="noreferrer">Swagger <span aria-hidden="true">↗</span></a>
<a class="api-link" href={`${api}/changelog`} target="_blank" rel="noreferrer">Changelog <span aria-hidden="true">↗</span></a>

<style>
  .api-link { color: #2c594c; font-size: 13px; font-weight: 600; text-decoration: none; }
  .api-link:hover { text-decoration: underline; }
</style>
