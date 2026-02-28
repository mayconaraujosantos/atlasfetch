"""Porta: API de débitos Aegea."""

from abc import ABC, abstractmethod


class DebitoApiPort(ABC):
    """Interface para buscar débitos na API Aegea."""

    @abstractmethod
    def buscar_debitos(
        self,
        access_token: str,
        matricula: str,
        sequencial_responsavel: str,
        zona_ligacao: str = "1",
    ) -> dict:
        """Busca débitos totais. Retorna JSON da API."""
        ...
