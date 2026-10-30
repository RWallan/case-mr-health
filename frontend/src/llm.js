// Lógica pura da seleção de LLM da seção Recomendações (#44).

export const PROVEDORES = [
  { id: 'openai', rotulo: 'OpenAI', exemplo: 'gpt-4o' },
  { id: 'anthropic', rotulo: 'Anthropic', exemplo: 'claude-sonnet-5-5' },
  { id: 'gemini', rotulo: 'Gemini', exemplo: 'gemini-2.0-flash' },
  { id: 'mistral', rotulo: 'Mistral', exemplo: 'mistral-large-latest' },
  { id: 'outro', rotulo: 'Outro (provedor/modelo)', exemplo: 'provedor/modelo' },
];

// Formato aceito pelo backend em X-LLM-Modelo: `provedor/modelo`.
const FORMATO = /^[^/\s]+\/\S+$/;

export function montarModelo(provedor, modelo) {
  const nome = (modelo ?? '').trim();
  if (!nome) return '';
  // "Outro": o usuário digita o `provedor/modelo` completo.
  return provedor === 'outro' ? nome : `${provedor}/${nome}`;
}

export function modeloValido(valor) {
  return FORMATO.test(valor);
}

// Cabeçalhos por requisição. Sem chave ou com modelo inválido, nenhum:
// a explicação cai no template (ou na configuração do servidor).
export function cabecalhosLlm(provedor, modelo, chave) {
  const segredo = (chave ?? '').trim();
  const composto = montarModelo(provedor, modelo);
  if (!segredo || !modeloValido(composto)) return {};
  return { 'X-LLM-Modelo': composto, 'X-LLM-Chave': segredo };
}

// Mensagem para o SKU quando a explicação veio do template mesmo com chave.
export function avisoTemplate(origem, usouLlm) {
  if (origem === 'template' && usouLlm) {
    return 'O LLM falhou ou foi rejeitado; esta explicação veio do template determinístico.';
  }
  return '';
}
