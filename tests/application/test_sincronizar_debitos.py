from atlasfetch.application.use_cases.sincronizar_debitos import SincronizarDebitosUseCase
from atlasfetch.domain.entities.auth_result import AuthResult


class FakeAuth:
    def __init__(self, result: AuthResult):
        self.result = result

    def login(self, cpf: str, senha: str, headless: bool = True):
        return self.result


class FakeDebitoApi:
    def __init__(self, response: dict):
        self.response = response
        self.calls = []

    def buscar_debitos(
        self,
        access_token: str,
        matricula: str,
        sequencial_responsavel: str,
        zona_ligacao: str,
    ):
        self.calls.append(
            {
                "access_token": access_token,
                "matricula": matricula,
                "sequencial_responsavel": sequencial_responsavel,
                "zona_ligacao": zona_ligacao,
            }
        )
        return self.response


class FakeRepository:
    def __init__(self, consultas: list[object]):
        self.consultas = consultas
        self.calls = []

    def salvar_por_referencia(
        self,
        data: dict,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ) -> list:
        self.calls.append(
            {
                "data": data,
                "matricula": matricula,
                "sequencial": sequencial,
                "zona_ligacao": zona_ligacao,
            }
        )
        return self.consultas


def test_execute_retorna_quantidade_de_consultas_salvas():
    auth = FakeAuth(
        AuthResult(
            access_token="token-xyz",
            matricula="mat-login",
            sequencial_responsavel="seq-login",
            zona_ligacao="4",
        )
    )
    debito_api = FakeDebitoApi({"content": {"debitos": [{"referencia": "03/2026"}]}})
    repository = FakeRepository([object(), object()])
    use_case = SincronizarDebitosUseCase(auth=auth, debito_api=debito_api, repository=repository)

    result = use_case.execute(
        cpf="123",
        senha="segredo",
        matricula="",
        sequencial="",
        zona="",
    )

    assert result == {"status": "ok", "consultas_salvas": 2}
    assert debito_api.calls == [
        {
            "access_token": "token-xyz",
            "matricula": "mat-login",
            "sequencial_responsavel": "seq-login",
            "zona_ligacao": "4",
        }
    ]
    assert repository.calls == [
        {
            "data": {"content": {"debitos": [{"referencia": "03/2026"}]}},
            "matricula": "mat-login",
            "sequencial": "seq-login",
            "zona_ligacao": 4,
        }
    ]


def test_execute_falha_quando_login_nao_retornou_identificadores():
    auth = FakeAuth(AuthResult(access_token="token-xyz"))
    debito_api = FakeDebitoApi({"content": {"debitos": []}})
    repository = FakeRepository([])
    use_case = SincronizarDebitosUseCase(auth=auth, debito_api=debito_api, repository=repository)

    try:
        use_case.execute(
            cpf="123",
            senha="segredo",
            matricula="",
            sequencial="",
        )
    except ValueError as exc:
        assert str(exc) == "Matrícula/sequencial não obtidos"
    else:
        raise AssertionError("Era esperado ValueError quando login não retorna dados mínimos")

    assert debito_api.calls == []
    assert repository.calls == []