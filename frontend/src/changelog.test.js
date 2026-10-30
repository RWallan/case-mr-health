import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatarData, formatarIssues, prepararVersoes, rotaDoHash } from './changelog.js';

test('rotaDoHash reconhece só #/changelog', () => {
  assert.equal(rotaDoHash('#/changelog'), 'changelog');
  assert.equal(rotaDoHash(''), 'inicio');
  assert.equal(rotaDoHash('#/outra'), 'inicio');
});

test('formatarData converte ISO para dd/mm/aaaa', () => {
  assert.equal(formatarData('2026-10-30'), '30/10/2026');
  assert.equal(formatarData('texto'), 'texto');
});

test('formatarIssues usa #NN como texto simples', () => {
  assert.equal(formatarIssues([8, 12]), '#8, #12');
  assert.equal(formatarIssues([]), '');
});

test('prepararVersoes mantém a ordem e descarta seções vazias', () => {
  const corpo = {
    versoes: [
      { versao: '0.4.0', data: '2026-10-30', secoes: [
        { tipo: 'Adicionado', itens: [{ texto: 'a', issues: [3] }] },
        { tipo: 'Interno', itens: [] },
      ] },
      { versao: '0.3.0', data: '2026-10-01', secoes: [] },
    ],
  };
  const r = prepararVersoes(corpo);
  assert.deepEqual(r.map((v) => v.versao), ['0.4.0', '0.3.0']);
  assert.equal(r[0].secoes.length, 1);
  assert.equal(r[0].secoes[0].itens[0].issues, '#3');
  assert.equal(r[0].data, '30/10/2026');
});

test('prepararVersoes aceita corpo vazio', () => {
  assert.deepEqual(prepararVersoes({ versoes: [] }), []);
  assert.deepEqual(prepararVersoes(null), []);
});
