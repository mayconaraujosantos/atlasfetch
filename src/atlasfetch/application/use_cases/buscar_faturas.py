"""Caso de uso: buscar faturas por ano/mês."""

from atlasfetch.domain.ports.auth_port import AuthPort
from atlasfetch.domain.ports.consulta_repository_port import ConsultaRepositoryPort
from atlasfetch.domain.ports.debito_api_port import DebitoApiPort
from atlasfetch.domain.value_objects.referencia import referencia_match


class BuscarFaturasUseCase:
    """Busca faturas: login → API Aegea → salva no banco → retorna filtrado."""

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
        ano: int,
        mes: int,
        cpf: str,
        senha: str,
        matricula: str,
        sequencial: str,
        zona: str = "1",
    ) -> dict:
        """Executa busca e retorna content com débitos filtrados."""
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

        self._repository.salvar_consulta_com_debitos(
            data, ano, mes, matricula=mat, sequencial=seq
        )

        content = data.get("content", {})
        debitos = content.get("debitos", [])
        debitos_filtrados = [
            d for d in debitos
            if referencia_match(d.get("referencia", ""), ano, mes)
        ]

        return {"content": {**content, "debitos": debitos_filtrados}}
