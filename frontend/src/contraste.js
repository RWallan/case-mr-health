// Contraste WCAG 2.x entre os tokens de cor (#45). Lógica pura, sem DOM.

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

/** Lê `--nome: #valor;` de um CSS e devolve {nome: '#valor'} (só cores hex). */
export function lerTokens(css) {
  const tokens = {};
  for (const [, nome, valor] of css.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    const limpo = valor.trim();
    if (HEX.test(limpo)) tokens[nome] = limpo;
  }
  return tokens;
}

function canais(cor) {
  let corpo = cor.slice(1);
  if (corpo.length === 3) corpo = [...corpo].map((c) => c + c).join('');
  return [0, 2, 4].map((i) => parseInt(corpo.slice(i, i + 2), 16) / 255);
}

export function luminancia(cor) {
  const [r, g, b] = canais(cor).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function razaoContraste(a, b) {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (claro + 0.05) / (escuro + 0.05);
}

/** Pares [primeiro plano, fundo, mínimo]: 4,5 para texto, 3 para não texto (WCAG 1.4.11). */
export const PARES = [
  ['--cor-texto', '--cor-fundo', 4.5],
  ['--cor-texto', '--cor-superficie', 4.5],
  ['--cor-texto-forte', '--cor-superficie', 4.5],
  ['--cor-texto-secundario', '--cor-superficie', 4.5],
  ['--cor-texto-secundario', '--cor-superficie-neutra', 4.5],
  ['--cor-texto-secundario', '--cor-neutro-fundo', 4.5],
  ['--cor-texto-suave', '--cor-superficie', 4.5],
  ['--cor-texto-suave', '--cor-fundo', 4.5],
  ['--cor-texto-suave', '--cor-superficie-neutra', 4.5],
  ['--cor-texto-suave', '--cor-neutro-fundo', 4.5],
  ['--cor-texto-suave', '--cor-lima-suave', 4.5],
  ['--cor-texto-sobre-escuro', '--cor-verde', 4.5],
  ['--cor-texto-sobre-escuro', '--cor-verde-escuro', 4.5],
  ['--cor-verde', '--cor-superficie', 4.5],
  ['--cor-verde', '--cor-lima-suave', 4.5],
  ['--cor-verde-escuro', '--cor-lima-suave', 4.5],
  ['--cor-verde-link', '--cor-superficie', 4.5],
  ['--cor-verde-link', '--cor-fundo', 4.5],
  ['--cor-verde-link', '--cor-lima-suave', 4.5],
  ['--cor-lima-texto', '--cor-lima-suave', 4.5],
  ['--cor-erro', '--cor-erro-fundo', 4.5],
  ['--cor-erro', '--cor-superficie', 4.5],
  ['--cor-alerta', '--cor-alerta-fundo', 4.5],
  ['--cor-alerta', '--cor-superficie', 4.5],
  ['--cor-alerta', '--cor-aumento-fundo', 4.5],
  ['--cor-aumento', '--cor-aumento-fundo', 4.5],
  ['--cor-info', '--cor-info-fundo', 4.5],
  ['--cor-sucesso', '--cor-sucesso-fundo', 4.5],
  ['--cor-sucesso', '--cor-superficie', 4.5],
  ['--cor-previsao-texto', '--cor-superficie', 4.5],
  ['--cor-borda-campo', '--cor-superficie', 3],
  ['--cor-foco', '--cor-superficie', 3],
  ['--cor-foco', '--cor-fundo', 3],
  ['--cor-historico', '--cor-superficie', 3],
  ['--cor-previsao', '--cor-superficie', 3],
  ['--cor-serie-1', '--cor-superficie', 3],
  ['--cor-serie-2', '--cor-superficie', 3],
  ['--cor-serie-3', '--cor-superficie', 3],
  ['--cor-serie-4', '--cor-superficie', 3],
  ['--cor-divisao', '--cor-superficie', 3],
];

/** Avalia os pares; devolve [{texto, fundo, minimo, razao, ok}]. */
export function avaliarPares(tokens, pares = PARES) {
  return pares.map(([texto, fundo, minimo]) => {
    const razao = razaoContraste(tokens[texto], tokens[fundo]);
    return { texto, fundo, minimo, razao, ok: razao >= minimo };
  });
}
