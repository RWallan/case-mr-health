import test from 'node:test';
import assert from 'node:assert/strict';
import { PROVEDORES, montarModelo, modeloValido, cabecalhosLlm, avisoTemplate } from './llm.js';

test('provedores do ticket estão na lista', () => {
  assert.deepEqual(PROVEDORES.map((p) => p.id), ['openai', 'anthropic', 'gemini', 'mistral', 'outro']);
});

test('provedor e modelo compõem provedor/modelo', () => {
  assert.equal(montarModelo('openai', ' gpt-4o '), 'openai/gpt-4o');
  assert.equal(montarModelo('gemini', 'gemini-2.0-flash'), 'gemini/gemini-2.0-flash');
});

test('"outro" usa o texto digitado como está', () => {
  assert.equal(montarModelo('outro', 'groq/llama-3'), 'groq/llama-3');
});

test('modelo vazio não compõe nada', () => {
  assert.equal(montarModelo('openai', '  '), '');
  assert.equal(montarModelo('openai', undefined), '');
});

test('modeloValido exige provedor/modelo', () => {
  assert.equal(modeloValido('openai/gpt-4o'), true);
  assert.equal(modeloValido('gpt-4o'), false);
  assert.equal(modeloValido('/gpt-4o'), false);
  assert.equal(modeloValido('openai/'), false);
  assert.equal(modeloValido('openai/gpt 4'), false);
});

test('cabeçalhos só com chave e modelo válidos', () => {
  assert.deepEqual(cabecalhosLlm('openai', 'gpt-4o', ' k-1 '), {
    'X-LLM-Modelo': 'openai/gpt-4o',
    'X-LLM-Chave': 'k-1',
  });
  assert.deepEqual(cabecalhosLlm('openai', 'gpt-4o', ''), {});
  assert.deepEqual(cabecalhosLlm('openai', '', 'k-1'), {});
  assert.deepEqual(cabecalhosLlm('outro', 'sem-barra', 'k-1'), {});
});

test('aviso de template só quando havia chave', () => {
  assert.match(avisoTemplate('template', true), /template/);
  assert.equal(avisoTemplate('template', false), '');
  assert.equal(avisoTemplate('llm', true), '');
});
