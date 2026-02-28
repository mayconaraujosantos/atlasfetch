"""Entidade: resultado da autenticação."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthResult:
    """Resultado do login com token e dados do cliente."""

    access_token: str
    matricula: str | None = None
    sequencial_responsavel: str | None = None
    zona_ligacao: str | None = None
