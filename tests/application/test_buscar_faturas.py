from atlasfetch.application.use_cases.buscar_faturas import BuscarFaturasUseCase
from atlasfetch.domain.entities.auth_result import AuthResult


class FakeAuth:
    def __init__(self, result: AuthResult):
        self.result = result
        self.calls = []

    def login(self, cpf: str, senha: str, headless: bool = True):
        self.calls.append(
            {"cpf": cpf, "senha": senha, "headless": headless}
        )
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
    def __init__(self):
        self.calls = []

    def salvar_consulta_com_debitos(
        self,
        data: dict,
        ano: int,
        mes: int,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ):
        self.calls.append(
            {
                "data": data,
                "ano": ano,
                "mes": mes,
                "matricula": matricula,
                "sequencial": sequencial,
                "zona_ligacao": zona_ligacao,
            }
        )


def test_execute_filtra_debitos_por_referencia_e_persiste_resultado():
    auth = FakeAuth(
        AuthResult(
            access_token="token-123",
            matricula="mat-login",
            sequencial_responsavel="seq-login",
            zona_ligacao="9",
        )
    )
    debito_api = FakeDebitoApi(
        {
            "content": {
                "debitos": [
                    {"referencia": "03/2026", "numeroAviso": 1, "valorFatura": 10.0},
                    {"referencia": "02/2026", "numeroAviso": 2, "valorFatura": 20.0},
                    {"referencia": "invalida", "numeroAviso": 3, "valorFatura": 30.0},
                ]
            }
        }
    )
    repository = FakeRepository()
    use_case = BuscarFaturasUseCase(auth=auth, debito_api=debito_api, repository=repository)

    result = use_case.execute(
        ano=2_026,
        mes=3,
        cpf="123",
        senha="segredo",
        matricula="",
        sequencial="",
        zona="",
    )

    assert len(repository.calls) == 1
    assert debito_api.calls == [
        {
            "access_token": "token-123",
            "matricula": "mat-login",
            "sequencial_responsavel": "seq-login",
            "zona_ligacao": "9",
        }
    ]
    assert result == {
        "content": {
            "debitos": [
                {"referencia": "03/2026", "numeroAviso": 1, "valorFatura": 10.0},
                {"referencia": "invalida", "numeroAviso": 3, "valorFatura": 30.0},
            ]
        }
    }


def test_execute_usa_dados_informados_quando_presentes():
    auth = FakeAuth(AuthResult(access_token="token-abc"))
    debito_api = FakeDebitoApi({"content": {"debitos": []}})
    repository = FakeRepository()
    use_case = BuscarFaturasUseCase(auth=auth, debito_api=debito_api, repository=repository)

    use_case.execute(
        ano=2_026,
        mes=3,
        cpf="123",
        senha="segredo",
        matricula="mat-manual",
        sequencial="seq-manual",
        zona="7",
    )

    assert debito_api.calls == [
        {
            "access_token": "token-abc",
            "matricula": "mat-manual",
            "sequencial_responsavel": "seq-manual",
            "zona_ligacao": "7",
        }
    ]
    assert repository.calls[0]["matricula"] == "mat-manual"
    assert repository.calls[0]["sequencial"] == "seq-manual"


def test_execute_falha_quando_matricula_ou_sequencial_nao_estao_disponiveis():
    auth = FakeAuth(AuthResult(access_token="token-abc"))
    debito_api = FakeDebitoApi({"content": {"debitos": []}})
    repository = FakeRepository()
    use_case = BuscarFaturasUseCase(auth=auth, debito_api=debito_api, repository=repository)

    try:
        use_case.execute(
            ano=2_026,
            mes=3,
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