"""
Interface base para scrapers de diferentes provedores (água, luz, escola, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ScraperResult:
    """Resultado genérico do scraper com token e dados do cliente."""

    access_token: str
    matricula: str | None = None
    sequencial_responsavel: str | None = None
    zona_ligacao: str | None = None
    # Campos extras para provedores específicos (ex: unit_id para luz)
    extra: dict[str, Any] | None = None


class BaseScraper(ABC):
    """Interface base para scrapers de faturas."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome do provedor (ex: aguas_manaus, amazonas_energia)."""
        ...

    @abstractmethod
    def login(
        self,
        documento: str,
        senha: str,
        *,
        headless: bool = True,
        **kwargs: Any,
    ) -> ScraperResult:
        """
        Realiza login e retorna token + dados do cliente.

        Args:
            documento: CPF ou CNPJ
            senha: Senha do usuário
            headless: Executar navegador em modo invisível
            **kwargs: Parâmetros específicos do provedor

        Returns:
            ScraperResult com access_token e dados
        """
        ...
