from sqlalchemy import create_engine
import pytest
from sqlalchemy.orm import sessionmaker

from atlasfetch.infrastructure.external.scrapers import educadventista as scraper
from atlasfetch.infrastructure.persistence import database as db


def test_sync_and_save_escola_persiste_parcelas_sem_browser(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'educadventista-sync.db'}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", session_local)
    db.Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(
        scraper,
        "login",
        lambda headless=False: {
            "parcelas": [
                {
                    "ReferenceDate": "maio/2026",
                    "BeneficiaryName": "Aluno Teste",
                    "TotalToPay": 199.9,
                    "dataValidadePix": "10/05/2099 12:30",
                    "codigoPix": "pix-escola-1",
                    "qrcodeBase64": "base64-1",
                },
                {
                    "ReferenceDate": "05/2026",
                    "BeneficiaryName": "Aluno Teste",
                    "TotalToPay": 250.0,
                    "dataValidadePix": "10/05/2099 12:30",
                    "codigoPix": "pix-escola-duplicado",
                    "qrcodeBase64": "base64-duplicado",
                },
                {
                    "ReferenceDate": "04/2026",
                    "BeneficiaryName": "Aluno Dois",
                    "Value": 180.0,
                    "codigoPIX": "pix-escola-2",
                    "qrcode_base64": "base64-2",
                    "DueDate": "2026/04/15 00:00:00",
                },
            ]
        },
    )

    try:
        result = scraper.sync_and_save_escola()
        itens = db.listar_faturas_escola(limit=10)
        periodos = db.listar_periodos_escola()
        abril = db.buscar_fatura_escola(2026, 4)
        maio = db.buscar_fatura_escola(2026, 5)

        assert result["salvos"] == 2
        assert result["parcelas"] == 3
        assert set(result["periodos"]) == {(2026, 4), (2026, 5)}
        assert [item["nome_aluno"] for item in itens] == ["Aluno Teste", "Aluno Dois"]
        assert [item["periodo"] for item in periodos] == ["05/2026", "04/2026"]
        assert maio is not None
        assert maio["quantidadeDebitos"] == 1
        assert maio["valorTotalDebitos"] == pytest.approx(199.9)
        assert maio["debitos"][0]["codigoPix"] == "pix-escola-1"
        assert abril is not None
        assert abril["debitos"][0]["codigoPix"] == "pix-escola-2"
    finally:
        engine.dispose()