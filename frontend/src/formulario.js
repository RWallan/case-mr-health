// Regras puras do formulário de previsão (#41), testáveis com `node --test`.

// Limite de períodos a prever e padrão, por granularidade (ADR 0011).
export const LIMITES = {
  diaria: { maximo: 14, padrao: 7, unidade: 'dias' },
  semanal: { maximo: 2, padrao: 2, unidade: 'semanas' },
};

export const limiteDe = (granularidade) => LIMITES[granularidade] ?? LIMITES.diaria;

export const horizontePadrao = (granularidade) => limiteDe(granularidade).padrao;

// Retorna a mensagem em português, ou '' se o horizonte é aceito.
export function validarHorizonte(horizonte, granularidade) {
  const { maximo, unidade } = limiteDe(granularidade);
  const valor = Number(horizonte);
  if (horizonte === '' || horizonte === null || !Number.isInteger(valor)) {
    return 'Informe um número inteiro de períodos.';
  }
  if (valor < 1) return 'Informe ao menos 1 período.';
  if (valor > maximo) return `O máximo é ${maximo} ${unidade} nesta granularidade.`;
  return '';
}

// Corpo de um item de previsão. Sem `dataManual`, a data é omitida e a API usa
// o fim do treino do modelo (ADR 0013). Com ela, é enviada como informada.
export function montarItem({ sku, granularidade, horizonte, dataManual = '' }) {
  const item = { sku, granularidade, horizonte: Number(horizonte) };
  if (dataManual) item.data_referencia = dataManual;
  return item;
}

// Campo do formulário apontado por um erro da API, ou '' se não se aplica.
// `campo` pode vir como 'horizonte' ou 'itens[0].horizonte' (lote).
export function campoDoErro(erro) {
  const campo = String(erro?.campo ?? '');
  if (/horizonte$/.test(campo)) return 'horizonte';
  if (/data_referencia$/.test(campo)) return 'data_referencia';
  if (/sku$/.test(campo)) return 'sku';
  if (erro?.codigo === 'horizonte_acima_do_limite') return 'horizonte';
  if (erro?.codigo === 'data_referencia_invalida') return 'data_referencia';
  return '';
}

// Mensagem clara para um erro da API (corpo `{codigo, mensagem, campo}`).
export function mensagemDoErro(erro, granularidade) {
  const { maximo, unidade } = limiteDe(granularidade);
  if (erro?.codigo === 'horizonte_acima_do_limite') {
    return `Peça no máximo ${maximo} ${unidade} à frente nesta granularidade. Reduza os períodos a prever.`;
  }
  if (erro?.codigo === 'data_referencia_invalida') {
    return `A data de referência informada não é válida: ela não pode ser anterior ao fim do treino do modelo, e a distância até o fim do treino somada aos períodos pedidos não pode passar de ${maximo} ${unidade}. Limpe a data para usar a referência automática.`;
  }
  return erro?.mensagem ?? 'Não foi possível gerar a previsão.';
}

// Para o lote, o erro útil está no primeiro detalhe que aponta um campo.
export function erroDoLote(corpo) {
  if (!corpo) return null;
  if (campoDoErro(corpo)) return corpo;
  const detalhe = (corpo.detalhes ?? []).find((d) => campoDoErro(d));
  return detalhe ? { ...corpo, campo: detalhe.campo } : corpo;
}
