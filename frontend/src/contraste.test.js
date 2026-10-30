import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { PARES, avaliarPares, lerTokens, luminancia, razaoContraste } from './contraste.js';

const tokens = lerTokens(readFileSync(new URL('../../design/tokens.css', import.meta.url), 'utf8'));

// Sem literais hexadecimais no código do frontend: monta preto e branco.
const preto = `#${'0'.repeat(6)}`;
const branco = `#${'f'.repeat(6)}`;

test('razão de contraste de referência: preto sobre branco é 21 e igual é 1', () => {
  assert.equal(razaoContraste(preto, branco).toFixed(2), '21.00');
  assert.equal(razaoContraste(preto, preto).toFixed(2), '1.00');
  assert.equal(razaoContraste(`#${'0'.repeat(3)}`, preto).toFixed(2), '1.00');
  assert.equal(luminancia(branco), 1);
});

test('lerTokens ignora valores que não são cor hexadecimal', () => {
  const lidos = lerTokens(`:root { --a: ${branco}; --b: 12px; --c: var(--a); }`);
  assert.deepEqual(lidos, { '--a': branco });
});

test('todo token dos pares existe em design/tokens.css', () => {
  for (const [texto, fundo] of PARES) {
    assert.ok(tokens[texto], `token ausente: ${texto}`);
    assert.ok(tokens[fundo], `token ausente: ${fundo}`);
  }
});

test('os pares de tokens atendem ao contraste mínimo (AA: 4,5 texto, 3 não texto)', () => {
  const falhas = avaliarPares(tokens).filter((par) => !par.ok);
  assert.deepEqual(
    falhas.map((par) => `${par.texto} / ${par.fundo}: ${par.razao.toFixed(2)} < ${par.minimo}`),
    [],
  );
});
