// Montagem da série do gráfico de previsão e regra da previsão toda zero (#38).
// Módulo puro: sem DOM nem Svelte, testado com `node --test`.

const DIA_MS = 86_400_000;

export const DIAS_POR_PERIODO = { diaria: 1, semanal: 7 };
// Períodos de histórico mostrados antes do início da previsão, na janela recente.
export const JANELA_RECENTE = { diaria: 28, semanal: 12 };

export const textoZero =
  'A previsão foi gerada, porém todos os valores previstos para a janela selecionada são iguais a zero.';
export const explicacaoZero =
  'Isso significa que o modelo estimou demanda zero para todos os períodos futuros da janela de previsão. Consulte o histórico e os dados de entrada para contextualizar esse resultado.';

export const paraMs = (data) => Date.parse(`${data}T00:00:00Z`);

// Todos os valores previstos exatamente 0, com lista não vazia. `null` não é zero.
export function previsaoTodaZero(periodos) {
  return (
    Array.isArray(periodos) &&
    periodos.length > 0 &&
    periodos.every((periodo) => periodo.quantidade_prevista === 0)
  );
}

const numero = (valor) => typeof valor === 'number' && Number.isFinite(valor);

// O intervalo só existe quando o backend calculou os dois limites.
function intervalo(inferior, superior) {
  return numero(inferior) && numero(superior) ? { inferior, superior } : null;
}

export function montarSerie({ historico = [], previsao = null, granularidade = 'diaria', janela = 'recente' }) {
  const periodos = previsao?.periodos ?? [];
  const inicioPrevisao = previsao?.data_referencia ? paraMs(previsao.data_referencia) : null;

  const completo = historico.map((ponto) => ({ data: ponto.data, ms: paraMs(ponto.data), valor: ponto.quantidade }));
  const ancora = inicioPrevisao ?? completo.at(-1)?.ms ?? null;
  const inicioJanela =
    janela === 'recente' && ancora !== null
      ? ancora - JANELA_RECENTE[granularidade] * DIAS_POR_PERIODO[granularidade] * DIA_MS
      : -Infinity;
  const visivel = completo.filter((ponto) => ponto.ms >= inicioJanela);

  const futuro = periodos.map((periodo) => ({
    data: periodo.data_alvo,
    ms: paraMs(periodo.data_alvo),
    valor: periodo.quantidade_prevista,
    intervalo80: intervalo(periodo.limite_inferior_80, periodo.limite_superior_80),
    intervalo95: intervalo(periodo.limite_inferior_95, periodo.limite_superior_95),
  }));

  const instantes = [...visivel.map((p) => p.ms), ...futuro.map((p) => p.ms), ...(inicioPrevisao === null ? [] : [inicioPrevisao])];
  let minimo = Math.min(...instantes);
  let maximo = Math.max(...instantes);
  if (!instantes.length) [minimo, maximo] = [0, 0];
  if (minimo === maximo) [minimo, maximo] = [minimo - DIA_MS, maximo + DIA_MS];

  const valores = [
    ...visivel.map((p) => p.valor),
    ...futuro.flatMap((p) => [p.valor, p.intervalo80?.superior, p.intervalo95?.superior].filter(numero)),
  ];
  const maior = Math.max(1, ...valores);

  return {
    historico: visivel,
    previsao: futuro,
    inicioPrevisao,
    fimPrevisao: futuro.at(-1)?.ms ?? null,
    dominio: [minimo, maximo],
    maximo: maior,
    teto: maior * 1.15,
    zero: previsaoTodaZero(periodos),
    vazio: visivel.length === 0 && futuro.length === 0,
    recortado: visivel.length < completo.length,
  };
}

// Escalas lineares: data (ms) para x e quantidade para y, dentro das margens.
export function escalas({ largura, altura, margem, dominio, teto }) {
  const [minimo, maximo] = dominio;
  const util = Math.max(1, largura - margem.esquerda - margem.direita);
  const alto = Math.max(1, altura - margem.topo - margem.base);
  return {
    x: (ms) => margem.esquerda + ((ms - minimo) / (maximo - minimo)) * util,
    y: (valor) => margem.topo + alto - (valor / teto) * alto,
  };
}

// Ponto (histórico ou previsto) mais próximo de um instante, para o tooltip.
export function pontoMaisProximo(serie, ms) {
  const candidatos = [
    ...serie.historico.map((ponto) => ({ ...ponto, tipo: 'historico' })),
    ...serie.previsao.map((ponto) => ({ ...ponto, tipo: 'previsao' })),
  ];
  let melhor = null;
  for (const ponto of candidatos) {
    const distancia = Math.abs(ponto.ms - ms);
    if (melhor === null || distancia < melhor.distancia) melhor = { ponto, distancia };
  }
  return melhor?.ponto ?? null;
}

// Instantes para os rótulos do eixo x, igualmente espaçados.
export function marcasDoEixo([minimo, maximo], quantidade) {
  if (quantidade < 2) return [minimo];
  return Array.from({ length: quantidade }, (_, i) => minimo + ((maximo - minimo) * i) / (quantidade - 1));
}
