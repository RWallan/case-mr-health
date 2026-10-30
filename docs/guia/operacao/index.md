# Operação

Como instalar, configurar, executar, testar e manter o sistema, e como
conferir a API pelo Swagger.

| Página | Conteúdo |
| --- | --- |
| [Instalação e configuração](instalacao.md) | Pré-requisitos, instalação, `CASE_MR_HEALTH_*`, `.env` e `VITE_*` |
| [Execução, testes e logs](execucao.md) | `poe app`, cada serviço, testes, logs e Swagger |
| [Retreino e troubleshooting](retreino-e-troubleshooting.md) | Retreino, manutenção, problemas comuns e lacunas |

## Como ler os comandos

Cada comando traz uma marca:

- **Verificado**: executado ao escrever esta página (ver o registro em
  `docs/relatorio/onda6/50.md`).
- **Não verificado**: não foi executado (sobe servidor, treina ou escreve em
  `data/mlflow`); o texto vem do código e do README.

!!! warning "Docker e deploy não existem"
    O repositório não tem Dockerfile, Docker Compose nem procedimento de
    deploy. Não há instruções de contêiner nem de publicação do serviço aqui,
    e elas não devem ser deduzidas desta documentação. Veja
    [lacunas](retreino-e-troubleshooting.md#lacunas).
