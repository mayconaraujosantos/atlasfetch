"""Adaptador: autenticação via Azure B2C (Playwright + 2FA)."""

from atlasfetch.domain.entities.auth_result import AuthResult
from atlasfetch.domain.ports.auth_port import AuthPort


class B2CAuthAdapter(AuthPort):
    """Implementa AuthPort usando Playwright e leitura de e-mail para 2FA."""

    def login(self, cpf: str, senha: str, *, headless: bool = True) -> AuthResult:
        from scraper import login as _login

        result = _login(cpf=cpf, senha=senha, headless=headless)
        return AuthResult(
            access_token=result.access_token,
            matricula=result.matricula,
            sequencial_responsavel=result.sequencial_responsavel,
            zona_ligacao=result.zona_ligacao,
        )
