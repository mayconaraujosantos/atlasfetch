"""Porta: autenticação no sistema Águas de Manaus."""

from abc import ABC, abstractmethod

from atlasfetch.domain.entities.auth_result import AuthResult


class AuthPort(ABC):
    """Interface para autenticação (login B2C + 2FA)."""

    @abstractmethod
    def login(self, cpf: str, senha: str, *, headless: bool = True) -> AuthResult:
        """Realiza login e retorna token + dados do cliente."""
        ...
