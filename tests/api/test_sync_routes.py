from atlasfetch.api.routes import sync


class FakeSyncUseCase:
    def __init__(self, response: dict):
        self.response = response
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def raise_luz_error():
    raise RuntimeError("falha luz")


def test_run_sync_aguas_retorna_resultado_do_use_case(api_client, monkeypatch):
    use_case = FakeSyncUseCase({"status": "ok", "consultas_salvas": 2})
    monkeypatch.setattr(
        sync,
        "get_config",
        lambda: {
            "cpf": "123",
            "senha": "segredo",
            "matricula": "mat-1",
            "sequencial": "seq-1",
            "zona": "7",
        },
    )
    monkeypatch.setattr(sync, "_create_sincronizar_debitos", lambda: use_case)

    response = api_client.post("/api/sync/run", params={"provedor": "aguas"})

    assert response.status_code == 200
    assert response.json() == {"aguas": {"status": "ok", "consultas_salvas": 2}}
    assert use_case.calls == [
        {
            "cpf": "123",
            "senha": "segredo",
            "matricula": "mat-1",
            "sequencial": "seq-1",
            "zona": "7",
        }
    ]


def test_run_sync_aguas_retorna_erro_quando_config_ausente(api_client, monkeypatch):
    monkeypatch.setattr(
        sync,
        "get_config",
        lambda: {
            "cpf": "",
            "senha": "",
            "matricula": "mat-1",
            "sequencial": "seq-1",
            "zona": "1",
        },
    )

    response = api_client.post("/api/sync/run", params={"provedor": "aguas"})

    assert response.status_code == 500
    assert response.json()["detail"] == "AGUAS_CPF e AGUAS_SENHA não configurados"


def test_run_sync_todos_mantem_erros_parciais_de_luz_e_escola(api_client, monkeypatch):
    use_case = FakeSyncUseCase({"status": "ok", "consultas_salvas": 1})
    monkeypatch.setattr(
        sync,
        "get_config",
        lambda: {
            "cpf": "123",
            "senha": "segredo",
            "matricula": "mat-1",
            "sequencial": "seq-1",
            "zona": "1",
        },
    )
    monkeypatch.setattr(sync, "_create_sincronizar_debitos", lambda: use_case)

    import atlasfetch.infrastructure.external.scrapers as scrapers

    monkeypatch.setattr(
        scrapers,
        "sync_and_save_luz",
        raise_luz_error,
    )
    monkeypatch.delenv("EDUCADVENTISTA_CPF", raising=False)
    monkeypatch.delenv("EDUCADVENTISTA_DATA_NASCIMENTO", raising=False)

    response = api_client.post("/api/sync/run", params={"provedor": "todos"})

    assert response.status_code == 200
    assert response.json() == {
        "aguas": {"status": "ok", "consultas_salvas": 1},
        "luz": {"erro": "falha luz"},
        "escola": {"erro": "EDUCADVENTISTA_CPF e EDUCADVENTISTA_DATA_NASCIMENTO não configurados"},
    }


def test_run_sync_escola_retorna_erro_quando_env_nao_configurado(api_client, monkeypatch):
    monkeypatch.delenv("EDUCADVENTISTA_CPF", raising=False)
    monkeypatch.delenv("EDUCADVENTISTA_DATA_NASCIMENTO", raising=False)

    response = api_client.post("/api/sync/run", params={"provedor": "escola"})

    assert response.status_code == 500
    assert response.json()["detail"] == "EDUCADVENTISTA_CPF e EDUCADVENTISTA_DATA_NASCIMENTO não configurados"


def test_run_sync_escola_retorna_resultado_do_scraper(api_client, monkeypatch):
    monkeypatch.setenv("EDUCADVENTISTA_CPF", "123")
    monkeypatch.setenv("EDUCADVENTISTA_DATA_NASCIMENTO", "01/01/2000")

    import atlasfetch.infrastructure.external.scrapers as scrapers

    monkeypatch.setattr(
        scrapers,
        "sync_and_save_escola",
        lambda: {"salvos": 2, "parcelas": 3, "periodos": [(2026, 4), (2026, 5)]},
    )

    response = api_client.post("/api/sync/run", params={"provedor": "escola"})

    assert response.status_code == 200
    assert response.json() == {
        "escola": {"salvos": 2, "parcelas": 3, "periodos": [[2026, 4], [2026, 5]]}
    }