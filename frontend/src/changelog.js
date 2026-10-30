// Lógica pura da visão de changelog (#46): rota por hash e formatação.

export function rotaDoHash(hash) {
  return hash === '#/changelog' ? 'changelog' : 'inicio';
}

export function formatarData(iso) {
  const [ano, mes, dia] = String(iso).split('-');
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : String(iso);
}

export function formatarIssues(issues) {
  return (issues ?? []).map((id) => `#${id}`).join(', ');
}

// Descarta seções sem itens e acrescenta os textos já formatados; a ordem
// do arquivo é mantida, então versões novas aparecem sem mudar o frontend.
export function prepararVersoes(corpo) {
  return (corpo?.versoes ?? []).map((versao) => ({
    versao: versao.versao,
    data: formatarData(versao.data),
    secoes: (versao.secoes ?? [])
      .filter((secao) => secao.itens?.length)
      .map((secao) => ({
        tipo: secao.tipo,
        itens: secao.itens.map((item) => ({
          texto: item.texto,
          issues: formatarIssues(item.issues),
        })),
      })),
  }));
}
