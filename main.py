"""
Scraper Águas de Manaus - ponto de entrada principal.
"""

import logging
import os
import sys

from dotenv import load_dotenv

from scraper import login, fetch_debito_totais, ScraperResult

load_dotenv()


def _setup_logging() -> None:
    """Configura logging com nível via LOG_LEVEL (DEBUG, INFO, WARNING, ERROR)."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        stream=sys.stdout,
    )


def main() -> None:
    """Executa login e busca dados de faturas."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Iniciando scraper Águas de Manaus")

    result: ScraperResult = login(headless=True)  # Automação total, sem interface

    logger.info("Login realizado com sucesso")
    logger.debug("Token: %s...", result.access_token[:50] if result.access_token else "N/A")

    if result.matricula and result.sequencial_responsavel:
        logger.info("Buscando dados de débito (matrícula capturada automaticamente)")
        dados = fetch_debito_totais(
            access_token=result.access_token,
            matricula=result.matricula,
            sequencial_responsavel=result.sequencial_responsavel,
            zona_ligacao=result.zona_ligacao or "1",
        )
        logger.info("Dados de débito obtidos: %s", dados)
    else:
        # Fallback: usar valores do .env se não foram capturados
        matricula = os.environ.get("AGUAS_MATRICULA")
        sequencial = os.environ.get("AGUAS_SEQUENCIAL")
        if matricula and sequencial:
            logger.info("Buscando dados de débito (matrícula do .env)")
            dados = fetch_debito_totais(
                access_token=result.access_token,
                matricula=matricula,
                sequencial_responsavel=sequencial,
                zona_ligacao=os.environ.get("AGUAS_ZONA", "1"),
            )
            logger.info("Dados de débito obtidos: %s", dados)
        else:
            logger.warning(
                "Matrícula/sequencial não capturados. "
                "Defina AGUAS_MATRICULA e AGUAS_SEQUENCIAL no .env para buscar faturas."
            )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.getLogger(__name__).exception("Erro fatal: %s", e)
        raise
