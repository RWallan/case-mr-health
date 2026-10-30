// Regras puras do componente de upload (#43), testáveis com `node --test`.

export const EXTENSAO = '.xlsx';

// O backend (FastAPI/Starlette) não impõe limite de tamanho aos uploads de
// planilha: o arquivo é lido inteiro em memória. O limite abaixo é só do
// cliente, para recusar cedo um arquivo errado ou enorme. As planilhas reais
// têm cerca de 6 a 12 KB; 5 MiB deixa folga de centenas de vezes.
export const LIMITE_BYTES = 5 * 1024 * 1024;

export function formatarTamanho(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  if (bytes < 1024 * 1024) return `${fmt.format(bytes / 1024)} KB`;
  return `${fmt.format(bytes / (1024 * 1024))} MB`;
}

// Retorna a mensagem de erro em português, ou '' se o arquivo é aceito.
export function validarArquivo(arquivo, limite = LIMITE_BYTES) {
  if (!arquivo) return 'Nenhum arquivo selecionado.';
  if (!arquivo.name.toLowerCase().endsWith(EXTENSAO)) {
    return `Formato não aceito: envie um arquivo ${EXTENSAO}.`;
  }
  if (arquivo.size === 0) return 'O arquivo está vazio.';
  if (arquivo.size > limite) {
    return `O arquivo tem ${formatarTamanho(arquivo.size)}; o limite é ${formatarTamanho(limite)}.`;
  }
  return '';
}

// Escolhe o primeiro arquivo de uma lista (input ou arrastar e soltar).
export function primeiroArquivo(lista) {
  return lista && lista.length ? lista[0] : null;
}
