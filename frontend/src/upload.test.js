import assert from 'node:assert/strict';
import { test } from 'node:test';
import { LIMITE_BYTES, formatarTamanho, primeiroArquivo, validarArquivo } from './upload.js';

const arq = (name, size) => ({ name, size });

test('aceita .xlsx dentro do limite, sem diferenciar maiúsculas', () => {
  assert.equal(validarArquivo(arq('pedidos.xlsx', 1000)), '');
  assert.equal(validarArquivo(arq('PEDIDOS.XLSX', 1000)), '');
});

test('recusa extensão inválida com mensagem', () => {
  assert.match(validarArquivo(arq('pedidos.csv', 10)), /\.xlsx/);
  assert.match(validarArquivo(arq('xlsx', 10)), /Formato não aceito/);
});

test('recusa arquivo vazio e acima do limite; o limite exato passa', () => {
  assert.match(validarArquivo(arq('a.xlsx', 0)), /vazio/);
  assert.match(validarArquivo(arq('a.xlsx', LIMITE_BYTES + 1)), /limite é 5 MB/);
  assert.equal(validarArquivo(arq('a.xlsx', LIMITE_BYTES)), '');
});

test('recusa ausência de arquivo', () => {
  assert.match(validarArquivo(null), /Nenhum/);
});

test('formata o tamanho em B, KB e MB', () => {
  assert.equal(formatarTamanho(512), '512 B');
  assert.equal(formatarTamanho(1536), '1,5 KB');
  assert.equal(formatarTamanho(5 * 1024 * 1024), '5 MB');
});

test('primeiroArquivo trata lista vazia ou ausente', () => {
  assert.equal(primeiroArquivo(null), null);
  assert.equal(primeiroArquivo([]), null);
  assert.equal(primeiroArquivo(['x', 'y']), 'x');
});
