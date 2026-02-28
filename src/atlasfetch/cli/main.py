"""CLI principal - executa login e busca faturas."""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _setup_logging() -> None:
    """Configura logging via LOG_LEVEL."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, stream=sys.stdout)


def main() -> None:
    """Executa login e busca dados de faturas."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    from atlasfetch.api.container import get_config, _create_sincronizar_debitos

    config = get_config()
    if not config["cpf"] or not config["senha"]:
        logger.error("Defina AGUAS_CPF e AGUAS_SENHA no .env")
        sys.exit(1)

    logger.info("Iniciando scraper Águas de Manaus")

    use_case = _create_sincronizar_debitos()
    result = use_case.execute(
        cpf=config["cpf"],
        senha=config["senha"],
        matricula=config["matricula"],
        sequencial=config["sequencial"],
        zona=config["zona"],
    )

    logger.info("Concluído: %s", result)
