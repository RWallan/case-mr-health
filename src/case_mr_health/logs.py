import sys

from loguru import logger


def configurar_logs(nivel: str = 'INFO') -> None:
    logger.remove()
    logger.add(sys.stderr, level=nivel.upper())
