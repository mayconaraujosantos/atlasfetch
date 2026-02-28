"""Caso de uso: sincronizar débitos (job agendado)."""

from atlasfetch.domain.ports.auth_port import AuthPort
from atlasfetch.domain.ports.consulta_repository_port import ConsultaRepositoryPort
from atlasfetch.domain.ports.debito_api_port import DebitoApiPort


class SincronizarDebitosUseCase:
    """Sincroniza débitos: login → API Aegea → salva por referencia."""

    def __init__(
        self,
        auth: AuthPort,
        debito_api: DebitoApiPort,
        repository: ConsultaRepositoryPort,
    ):
        self._auth = auth
        self._debito_api = debito_api
        self._repository = repository

    def execute(
        self,
        cpf: str,
        senha: str,
        matricula: str,
        sequencial: str,
        zona: str = "1",
    ) -> dict:
        """Executa sync e retorna status + quantidade de consultas salvas."""
        result = self._auth.login(cpf, senha, headless=True)

        mat = matricula or result.matricula
        seq = sequencial or result.sequencial_responsavel
        zon = zona or (result.zona_ligacao or "1")

        if not mat or not seq:
            raise ValueError("Matrícula/sequencial não obtidos")

        data = self._debito_api.buscar_debitos(
            access_token=result.access_token,
            matricula=mat,
            sequencial_responsavel=seq,
            zona_ligacao=zon,
        )

        consultas = self._repository.salvar_por_referencia(
            data, matricula=mat, sequencial=seq,
            zona_ligacao=int(zon) if zon else 1
        )

        return {"status": "ok", "consultas_salvas": len(consultas)}
