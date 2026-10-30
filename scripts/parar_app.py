"""Libera as portas do app (API, MLflow, dashboard e docs) de imediato (#54).

O `poe app` deixa processos órfãos (uvicorn, workers do MLflow) quando é
interrompido; este script encerra quem escuta nas portas do app.
"""

import subprocess
import sys

from loguru import logger

PORTAS = {
    8000: 'API',
    5000: 'MLflow',
    5173: 'dashboard',
    8001: 'documentação',
}


def liberar(porta: int) -> bool:
    """Encerra quem escuta na porta (SIGKILL); False se estava livre."""
    resultado = subprocess.run(
        ['fuser', '-k', '-KILL', f'{porta}/tcp'],
        capture_output=True,
        check=False,
    )
    return resultado.returncode == 0


def main() -> None:
    for porta, nome in PORTAS.items():
        if liberar(porta):
            logger.info('Porta {} ({}) liberada.', porta, nome)
        else:
            logger.debug('Porta {} ({}) já estava livre.', porta, nome)


if __name__ == '__main__':
    sys.exit(main())
