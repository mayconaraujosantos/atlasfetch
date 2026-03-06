"""
Scraper para Águas de Manaus (água).
Encapsula o scraper existente em aguas_scraper.py.
"""

from atlasfetch.infrastructure.external.scrapers.base import BaseScraper, ScraperResult


class AguasManausScraper(BaseScraper):
    """Scraper para Águas de Manaus - login via Azure B2C e 2FA por e-mail."""

    @property
    def provider_name(self) -> str:
        return "aguas_manaus"

    def login(
        self,
        documento: str,
        senha: str,
        *,
        headless: bool = True,
        **kwargs,
    ) -> ScraperResult:
        from atlasfetch.infrastructure.external.aguas_scraper import login as _login

        result = _login(cpf=documento, senha=senha, headless=headless)
        return ScraperResult(
            access_token=result.access_token,
            matricula=result.matricula,
            sequencial_responsavel=result.sequencial_responsavel,
            zona_ligacao=result.zona_ligacao,
        )
