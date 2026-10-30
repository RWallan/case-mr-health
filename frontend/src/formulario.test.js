import assert from 'node:assert/strict';
import { test } from 'node:test';
import { campoDoErro, erroDoLote, horizontePadrao, limiteDe, mensagemDoErro, montarItem, validarHorizonte } from './formulario.js';

test('limites e padrões por granularidade', () => {
  assert.equal(limiteDe('diaria').maximo, 14);
  assert.equal(limiteDe('semanal').maximo, 2);
  assert.equal(horizontePadrao('diaria'), 7);
  assert.equal(horizontePadrao('semanal'), 2);
});

test('validarHorizonte respeita o limite da granularidade', () => {
  assert.equal(validarHorizonte(14, 'diaria'), '');
  assert.match(validarHorizonte(15, 'diaria'), /14 dias/);
  assert.equal(validarHorizonte(2, 'semanal'), '');
  assert.match(validarHorizonte(3, 'semanal'), /2 semanas/);
  assert.match(validarHorizonte(0, 'diaria'), /ao menos 1/);
  assert.match(validarHorizonte('', 'diaria'), /inteiro/);
  assert.match(validarHorizonte(1.5, 'diaria'), /inteiro/);
});

test('montarItem omite a data sem data manual', () => {
  const item = montarItem({ sku: 'item A', granularidade: 'diaria', horizonte: '7' });
  assert.deepEqual(item, { sku: 'item A', granularidade: 'diaria', horizonte: 7 });
  assert.ok(!('data_referencia' in item));
});

test('montarItem inclui a data manual quando informada', () => {
  const item = montarItem({ sku: 'item B', granularidade: 'semanal', horizonte: 2, dataManual: '2021-08-23' });
  assert.equal(item.data_referencia, '2021-08-23');
});

test('mensagens dos 422 em linguagem clara', () => {
  assert.match(mensagemDoErro({ codigo: 'horizonte_acima_do_limite' }, 'semanal'), /2 semanas/);
  assert.match(mensagemDoErro({ codigo: 'data_referencia_invalida' }, 'diaria'), /referência automática/);
  assert.equal(mensagemDoErro({ codigo: 'x', mensagem: 'falhou' }, 'diaria'), 'falhou');
});

test('campoDoErro aponta o campo, inclusive no lote', () => {
  assert.equal(campoDoErro({ campo: 'horizonte' }), 'horizonte');
  assert.equal(campoDoErro({ campo: 'itens[0].data_referencia' }), 'data_referencia');
  assert.equal(campoDoErro({ codigo: 'horizonte_acima_do_limite' }), 'horizonte');
  assert.equal(campoDoErro({ codigo: 'outro' }), '');
});

test('erroDoLote escolhe o detalhe que aponta um campo', () => {
  const corpo = { codigo: 'lote_invalido', mensagem: 'm', detalhes: [{ campo: 'itens[0].horizonte', mensagem: 'x' }] };
  assert.equal(campoDoErro(erroDoLote(corpo)), 'horizonte');
  assert.equal(erroDoLote(null), null);
});
