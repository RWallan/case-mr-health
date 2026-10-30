import assert from 'node:assert/strict';
import { test } from 'node:test';
import { escalas, marcasDoEixo, montarSerie, paraMs, pontoMaisProximo, previsaoTodaZero } from './grafico.js';

const periodo = (data_alvo, quantidade_prevista, extra = {}) => ({
  data_alvo,
  quantidade_prevista,
  valor_previsto: 0,
  limite_inferior_80: null,
  limite_superior_80: null,
  limite_inferior_95: null,
  limite_superior_95: null,
  ...extra,
});

const historicoDiario = (inicio, quantidade) =>
  Array.from({ length: quantidade }, (_, i) => ({
    data: new Date(paraMs(inicio) + i * 86_400_000).toISOString().slice(0, 10),
    quantidade: i + 1,
  }));

test('regra do zero: só dispara com todos os valores exatamente 0', () => {
  assert.equal(previsaoTodaZero([periodo('2021-08-19', 0), periodo('2021-08-20', 0)]), true);
  assert.equal(previsaoTodaZero([periodo('2021-08-19', 0), periodo('2021-08-20', 3)]), false);
  assert.equal(previsaoTodaZero([periodo('2021-08-19', 0.4)]), false);
});

test('regra do zero: lista vazia, ausente e null não contam como zero', () => {
  assert.equal(previsaoTodaZero([]), false);
  assert.equal(previsaoTodaZero(undefined), false);
  assert.equal(previsaoTodaZero(null), false);
  assert.equal(previsaoTodaZero([periodo('2021-08-19', null)]), false);
  assert.equal(previsaoTodaZero([periodo('2021-08-19', 0), periodo('2021-08-20', null)]), false);
});

test('o alerta independe do histórico estar zerado ou não', () => {
  const previsao = { data_referencia: '2021-08-18', periodos: [periodo('2021-08-19', 0)] };
  const zerado = historicoDiario('2021-08-01', 10).map((p) => ({ ...p, quantidade: 0 }));

  assert.equal(montarSerie({ historico: zerado, previsao }).zero, true);
  assert.equal(montarSerie({ historico: historicoDiario('2021-08-01', 10), previsao }).zero, true);
  assert.equal(montarSerie({ historico: historicoDiario('2021-08-01', 10), previsao: null }).zero, false);
});

test('a previsão fica na data de cada período, não depois do histórico', () => {
  // Base vai até 2021-09-01, mas a referência é 2021-08-18: a previsão começa antes do fim do histórico.
  const historico = historicoDiario('2021-07-01', 63);
  const previsao = { data_referencia: '2021-08-18', periodos: [periodo('2021-08-19', 5), periodo('2021-08-20', 6)] };

  const serie = montarSerie({ historico, previsao, granularidade: 'diaria', janela: 'completo' });
  const { x } = escalas({ largura: 900, altura: 280, margem: { esquerda: 40, direita: 10, topo: 10, base: 30 }, dominio: serie.dominio, teto: serie.teto });

  assert.equal(historico.at(-1).data, '2021-09-01');
  assert.deepEqual(serie.previsao.map((p) => p.data), ['2021-08-19', '2021-08-20']);
  assert.ok(x(serie.previsao[0].ms) < x(serie.historico.at(-1).ms));
  assert.equal(serie.inicioPrevisao, paraMs('2021-08-18'));
  const ontem = serie.historico.find((p) => p.data === '2021-08-18');
  assert.ok(x(ontem.ms) < x(serie.previsao[0].ms));
});

test('intervalo ausente (null) não é desenhado nem estimado', () => {
  const previsao = {
    data_referencia: '2021-08-18',
    periodos: [
      periodo('2021-08-19', 7),
      periodo('2021-08-20', 8, { limite_inferior_80: 1, limite_superior_80: 12, limite_inferior_95: null, limite_superior_95: 20 }),
    ],
  };

  const serie = montarSerie({ historico: [], previsao });

  assert.equal(serie.previsao[0].intervalo80, null);
  assert.equal(serie.previsao[0].intervalo95, null);
  assert.deepEqual(serie.previsao[1].intervalo80, { inferior: 1, superior: 12 });
  assert.equal(serie.previsao[1].intervalo95, null);
  // O limite superior de 95% sem o inferior não entra no teto do eixo.
  assert.equal(serie.maximo, 12);
});

test('limite 0 é um intervalo válido, diferente de ausente', () => {
  const previsao = {
    data_referencia: '2021-08-18',
    periodos: [periodo('2021-08-19', 4, { limite_inferior_95: 0, limite_superior_95: 9, limite_inferior_80: 0, limite_superior_80: 6 })],
  };

  const serie = montarSerie({ historico: [], previsao });

  assert.deepEqual(serie.previsao[0].intervalo95, { inferior: 0, superior: 9 });
});

test('janela recente corta o histórico antes do início da previsão; completo mantém tudo', () => {
  const historico = historicoDiario('2021-05-01', 110); // até 2021-08-18
  const previsao = { data_referencia: '2021-08-18', periodos: [periodo('2021-08-19', 3)] };

  const recente = montarSerie({ historico, previsao, granularidade: 'diaria' });
  const completo = montarSerie({ historico, previsao, granularidade: 'diaria', janela: 'completo' });

  assert.equal(recente.historico.length, 29); // 28 dias antes da referência, mais a própria referência
  assert.equal(recente.historico[0].data, '2021-07-21');
  assert.equal(recente.recortado, true);
  assert.equal(completo.historico.length, 110);
  assert.equal(completo.recortado, false);
});

test('janela semanal conta em semanas', () => {
  const historico = Array.from({ length: 40 }, (_, i) => ({
    data: new Date(paraMs('2021-01-04') + i * 7 * 86_400_000).toISOString().slice(0, 10),
    quantidade: i,
  }));
  const ultimo = historico.at(-1).data;
  const previsao = { data_referencia: ultimo, periodos: [periodo('2021-10-04', 1)] };

  const serie = montarSerie({ historico, previsao, granularidade: 'semanal' });

  assert.equal(serie.historico.length, 13);
});

test('sem dados: série vazia, sem alerta e sem quebrar', () => {
  const serie = montarSerie({ historico: [], previsao: null });

  assert.equal(serie.vazio, true);
  assert.equal(serie.zero, false);
  assert.equal(serie.inicioPrevisao, null);
  assert.ok(serie.dominio[0] < serie.dominio[1]);
  assert.ok(serie.teto > 0);
});

test('sem previsão, a janela recente ancora no último ponto do histórico', () => {
  const serie = montarSerie({ historico: historicoDiario('2021-05-01', 110), previsao: null });

  assert.equal(serie.historico.length, 29);
  assert.equal(serie.previsao.length, 0);
});

test('ponto mais próximo serve o tooltip e distingue histórico de previsão', () => {
  const previsao = { data_referencia: '2021-08-18', periodos: [periodo('2021-08-19', 5)] };
  const serie = montarSerie({ historico: historicoDiario('2021-08-01', 18), previsao });

  assert.equal(pontoMaisProximo(serie, paraMs('2021-08-19') + 3_600_000).tipo, 'previsao');
  assert.equal(pontoMaisProximo(serie, paraMs('2021-08-10')).data, '2021-08-10');
  assert.equal(pontoMaisProximo({ historico: [], previsao: [] }, 0), null);
});

test('marcas do eixo são igualmente espaçadas', () => {
  assert.deepEqual(marcasDoEixo([0, 100], 3), [0, 50, 100]);
});
