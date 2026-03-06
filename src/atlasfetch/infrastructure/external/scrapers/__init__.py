"""
Módulos de scraper por provedor (água, luz, escola, etc.).
Cada provedor implementa a interface base e expõe login + busca de dados.
"""

from atlasfetch.infrastructure.external.scrapers.base import BaseScraper, ScraperResult
from atlasfetch.infrastructure.external.scrapers.aguas_manaus import AguasManausScraper
from atlasfetch.infrastructure.external.scrapers.amazonas_energia import (
    AmazonasEnergiaScraper,
    fetch_faturas_abertas,
    fetch_consumes,
    fetch_consumes_scheduled,
    get_stored_token,
    get_unit_ids,
    login as amazonas_energia_login,
    login_and_fetch_faturas_abertas,
    sync_and_save_luz,
)
from atlasfetch.infrastructure.external.scrapers.educadventista import (
    EducadventistaScraper,
    login as educadventista_login,
    sync_and_save_escola,
)

__all__ = [
    "BaseScraper",
    "ScraperResult",
    "AguasManausScraper",
    "AmazonasEnergiaScraper",
    "EducadventistaScraper",
    "amazonas_energia_login",
    "login_and_fetch_faturas_abertas",
    "fetch_faturas_abertas",
    "educadventista_login",
    "fetch_consumes",
    "fetch_consumes_scheduled",
    "get_stored_token",
    "get_unit_ids",
    "sync_and_save_luz",
    "sync_and_save_escola",
]
