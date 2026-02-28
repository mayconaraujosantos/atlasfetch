"""Adaptador: cliente da API Aegea para débitos."""

from atlasfetch.domain.ports.debito_api_port import DebitoApiPort


class AegeaDebitoClient(DebitoApiPort):
    """Implementa DebitoApiPort usando requests à API Aegea."""

    def buscar_debitos(
        self,
        access_token: str,
        matricula: str,
        sequencial_responsavel: str,
        zona_ligacao: str = "1",
    ) -> dict:
        from scraper import fetch_debito_totais

        return fetch_debito_totais(
            access_token=access_token,
            matricula=matricula,
            sequencial_responsavel=sequencial_responsavel,
            zona_ligacao=zona_ligacao,
        )
