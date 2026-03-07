import json

import pytest

from atlasfetch.api.routes import faturas
from atlasfetch.infrastructure.persistence import database as db
from atlasfetch.infrastructure.persistence.sqlalchemy_repository import SqlAlchemyConsultaRepository


class FakeRepository:
    def __init__(self, periodos=None, consulta=None):
        self._periodos = periodos or []
        self._consulta = consulta

    def listar_periodos_disponiveis(self):
        return self._periodos

    def buscar_ultima_consulta(self, ano: int, mes: int):
        return self._consulta


def test_healthcheck_retorna_status_ok(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_listar_periodos_aguas_retorna_dados_do_repositorio(api_client, monkeypatch):
    repository = FakeRepository(
        periodos=[
            {
                "ano": 2026,
                "mes": 3,
                "periodo": "03/2026",
                "valorTotal": 25.0,
                "quantidadeDebitos": 2,
                "existeDebitoVencido": True,
            }
        ]
    )
    monkeypatch.setattr(faturas, "get_repository", lambda: repository)

    response = api_client.get("/api/faturas", params={"provedor": "aguas"})

    assert response.status_code == 200
    assert response.json() == {
        "periodos": [
            {
                "ano": 2026,
                "mes": 3,
                "periodo": "03/2026",
                "valorTotal": 25.0,
                "quantidadeDebitos": 2,
                "existeDebitoVencido": True,
                "provedor": "aguas",
            }
        ]
    }


def test_listar_periodos_todos_mescla_e_ordena_provedores(api_client, monkeypatch):
    repository = FakeRepository(
        periodos=[
            {
                "ano": 2026,
                "mes": 2,
                "periodo": "02/2026",
                "valorTotal": 10.0,
                "quantidadeDebitos": 1,
                "existeDebitoVencido": False,
            }
        ]
    )
    monkeypatch.setattr(faturas, "get_repository", lambda: repository)
    monkeypatch.setattr(db, "listar_periodos_luz", lambda: [{
        "ano": 2026,
        "mes": 3,
        "periodo": "03/2026",
        "valorTotal": 90.0,
        "quantidadeDebitos": 1,
        "existeDebitoVencido": False,
    }])
    monkeypatch.setattr(db, "listar_periodos_escola", lambda: [{
        "ano": 2025,
        "mes": 12,
        "periodo": "12/2025",
        "valorTotal": 150.0,
        "quantidadeDebitos": 1,
        "existeDebitoVencido": False,
    }])

    response = api_client.get("/api/faturas", params={"provedor": "todos"})

    assert response.status_code == 200
    assert [item["provedor"] for item in response.json()["periodos"]] == [
        "luz",
        "aguas",
        "escola",
    ]


def test_get_fatura_retorna_resumo_e_debitos_formatados(api_client, monkeypatch):
    repository = FakeRepository(
        consulta={
            "valorTotalDebitos": 62.57,
            "quantidadeDebitos": 1,
            "existeDebitoVencido": False,
            "consultadoEm": "2026-03-06T10:00:00",
            "debitos": [
                {
                    "numeroAviso": 160408916,
                    "referencia": "03/2026",
                    "valorFatura": 62.57,
                    "dataVencimento": "2026-03-10T00:00:00",
                    "codigoBarrasDigitavel": "8265000000036257",
                    "codigoPIX": "pix-copia-cola",
                    "statusFatura": "Em Aberto",
                    "situacaoPagamento": "D",
                }
            ],
        }
    )
    monkeypatch.setattr(faturas, "get_repository", lambda: repository)

    response = api_client.get("/api/faturas/2026/3")

    assert response.status_code == 200
    body = response.json()
    assert body["resumo"] == {
        "periodo": "03/2026",
        "ano": 2026,
        "mes": 3,
        "valorTotal": 62.57,
        "quantidadeDebitos": 1,
        "existeDebitoVencido": False,
        "consultadoEm": "2026-03-06T10:00:00",
    }
    assert body["debitos"] == [
        {
            "id": 160408916,
            "referencia": "03/2026",
            "valor": 62.57,
            "dataVencimento": "2026-03-10T00:00:00",
            "codigoBarras": "8265000000036257",
            "codigoPix": "pix-copia-cola",
            "status": "Em Aberto",
            "situacaoPagamento": "D",
        }
    ]


def test_listar_periodos_rejeita_provedor_invalido(api_client):
    response = api_client.get("/api/faturas", params={"provedor": "gas"})

    assert response.status_code == 400
    assert response.json()["detail"] == "provedor inválido. Use: aguas, luz, escola, todos ou ambos"


def test_get_fatura_aguas_ler_dado_persistido_no_banco(integration_client):
    repository = SqlAlchemyConsultaRepository(get_session=db.SessionLocal)
    repository.salvar_consulta_com_debitos(
        {
            "content": {
                "debitos": [
                    {
                        "referencia": "03/2026",
                        "dataVencimento": "2026-03-10T00:00:00Z",
                        "valorFatura": 62.57,
                        "situacaoPagamento": "D",
                        "codigoTributo": "123",
                        "anoLancamento": 2026,
                        "numeroAviso": 160408916,
                        "numeroEmissao": 1,
                        "zonaLigacao": 1,
                        "statusFatura": "Em Aberto",
                        "consumo": 15,
                        "codigoBarrasDigitavel": "8265000000036257",
                        "codigoPIX": "pix-copia-cola",
                        "contratoEncerrado": False,
                    }
                ]
            }
        },
        ano=2026,
        mes=3,
        matricula="matricula-1",
        sequencial="seq-1",
    )

    response = integration_client.get("/api/faturas/2026/3", params={"provedor": "aguas"})

    assert response.status_code == 200
    body = response.json()
    assert body["resumo"]["periodo"] == "03/2026"
    assert body["resumo"]["valorTotal"] == pytest.approx(62.57)
    assert body["resumo"]["quantidadeDebitos"] == 1
    assert body["debitos"] == [
        {
            "id": 160408916,
            "referencia": "03/2026",
            "valor": 62.57,
            "dataVencimento": "2026-03-10T00:00:00",
            "codigoBarras": "8265000000036257",
            "codigoPix": "pix-copia-cola",
            "status": "Em Aberto",
            "situacaoPagamento": "D",
        }
    ]


def test_listar_periodos_luz_ler_registro_persistido_no_banco(integration_client):
    db.salvar_fatura_luz(
        unit_id="UC123",
        ano=2026,
        mes=4,
        data_json=json.dumps({"valorTotal": 91.2, "consumos": [{"ReferenceDate": "04/2026"}]}),
    )

    response = integration_client.get("/api/faturas", params={"provedor": "luz"})

    assert response.status_code == 200
    assert response.json() == {
        "periodos": [
            {
                "ano": 2026,
                "mes": 4,
                "periodo": "04/2026",
                "valorTotal": 91.2,
                "quantidadeDebitos": 1,
                "existeDebitoVencido": False,
                "provedor": "luz",
            }
        ]
    }


def test_get_fatura_escola_ler_dado_persistido_no_banco(integration_client):
    db.salvar_fatura_escola(
        nome_aluno="Aluno Teste",
        ano=2026,
        mes=5,
        valor=150.5,
        data_validade_pix="10/05/2099 12:30",
        codigo_pix="pix-escola",
        qrcode_base64="qrcode-em-base64",
    )

    response = integration_client.get("/api/faturas/2026/5", params={"provedor": "escola"})

    assert response.status_code == 200
    body = response.json()
    assert body["resumo"]["periodo"] == "05/2026"
    assert body["resumo"]["valorTotal"] == pytest.approx(150.5)
    assert body["resumo"]["quantidadeDebitos"] == 1
    assert body["debitos"] == [
        {
            "id": 1,
            "referencia": "05/2026",
            "valor": 150.5,
            "dataVencimento": "10/05/2099 12:30",
            "codigoBarras": "",
            "codigoPix": "pix-escola",
            "status": "Pago",
            "situacaoPagamento": "P",
        }
    ]


def test_listar_periodos_todos_ler_dados_reais_do_banco(integration_client):
    repository = SqlAlchemyConsultaRepository(get_session=db.SessionLocal)
    repository.salvar_consulta_com_debitos(
        {
            "content": {
                "debitos": [
                    {
                        "referencia": "03/2026",
                        "dataVencimento": "2026-03-10T00:00:00Z",
                        "valorFatura": 50.0,
                        "situacaoPagamento": "D",
                        "codigoTributo": "123",
                        "anoLancamento": 2026,
                        "numeroAviso": 3001,
                        "numeroEmissao": 1,
                        "zonaLigacao": 1,
                        "statusFatura": "Em Aberto",
                        "consumo": 10,
                        "codigoBarrasDigitavel": "123",
                        "codigoPIX": "pix-agua",
                        "contratoEncerrado": False,
                    }
                ]
            }
        },
        ano=2026,
        mes=3,
        matricula="matricula-1",
        sequencial="seq-1",
    )
    db.salvar_fatura_luz(
        unit_id="UC123",
        ano=2026,
        mes=4,
        data_json=json.dumps({"valorTotal": 91.2, "consumos": [{"ReferenceDate": "04/2026"}]}),
    )
    db.salvar_fatura_escola(
        nome_aluno="Aluno Teste",
        ano=2025,
        mes=12,
        valor=150.5,
        data_validade_pix="10/05/2099 12:30",
        codigo_pix="pix-escola",
        qrcode_base64="qrcode-em-base64",
    )

    response = integration_client.get("/api/faturas", params={"provedor": "todos"})

    assert response.status_code == 200
    assert response.json() == {
        "periodos": [
            {
                "ano": 2026,
                "mes": 4,
                "periodo": "04/2026",
                "valorTotal": 91.2,
                "quantidadeDebitos": 1,
                "existeDebitoVencido": False,
                "provedor": "luz",
            },
            {
                "ano": 2026,
                "mes": 3,
                "periodo": "03/2026",
                "valorTotal": 50.0,
                "quantidadeDebitos": 1,
                "existeDebitoVencido": False,
                "provedor": "aguas",
            },
            {
                "ano": 2025,
                "mes": 12,
                "periodo": "12/2025",
                "valorTotal": 150.5,
                "quantidadeDebitos": 1,
                "existeDebitoVencido": False,
                "provedor": "escola",
            },
        ]
    }


def test_get_fatura_retorna_404_real_quando_nao_ha_registro(integration_client):
    response = integration_client.get("/api/faturas/2030/1", params={"provedor": "aguas"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Nenhuma fatura encontrada para este período"