from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from atlasfetch.infrastructure.external.scrapers import amazonas_energia as scraper
from atlasfetch.infrastructure.persistence import database as db


def test_sync_and_save_luz_persiste_payload_da_agencia_em_tabelas_normalizadas(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'amazonas-sync.db'}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", session_local)
    db.Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(db, "get_amazonas_energia_token", lambda: ("Bearer fake-token", ""))
    monkeypatch.setattr(scraper, "get_unit_ids", lambda: ["UC123"])
    monkeypatch.setattr(scraper, "get_client_id", lambda: "client-123")
    monkeypatch.setattr(
        scraper,
        "fetch_faturas_abertas",
        lambda auth_header, unit_id, client_id: {
            "debitos": [
                {
                    "MES_ANO_REFERENCIA": "04/2026",
                    "ID_BOLETO": 555,
                    "DATA_VENCIMENTO": "2026-04-15",
                    "VALOR_TOTAL": 91.2,
                    "BOLETO": "linha-digitavel",
                    "CODIGO_BARRAS": "1234567890",
                    "PIX": "pix-luz",
                    "SITUACAO": "EM_ABERTO",
                    "DESCRICAO_SITUACAO": "Em aberto",
                    "VENCIDA": False,
                    "NUMERO_AME": "AME-1",
                },
                {
                    "MES_ANO_REFERENCIA": "03/2026",
                    "ID_BOLETO": 556,
                    "DATA_VENCIMENTO": "2026-03-15",
                    "VALOR_TOTAL": 88.4,
                    "BOLETO": "linha-digitavel-2",
                    "CODIGO_BARRAS": "0987654321",
                    "PIX": "pix-luz-2",
                    "SITUACAO": "EM_ABERTO",
                    "DESCRICAO_SITUACAO": "Em aberto",
                    "VENCIDA": True,
                    "NUMERO_AME": "AME-2",
                },
            ]
        },
    )

    session = None
    try:
        result = scraper.sync_and_save_luz()
        periodos_luz = db.listar_periodos_luz()
        fatura_abril = db.buscar_fatura_luz(2026, 4)
        session = db.SessionLocal()
        abertas = session.query(db.FaturaLuzAberta).order_by(db.FaturaLuzAberta.mes.desc()).all()

        assert result == {
            "salvos": 2,
            "unit_ids": ["UC123"],
            "resultados": [
                {
                    "unit_id": "UC123",
                    "salvos": 2,
                    "periodos": [(2026, 4), (2026, 3)],
                }
            ],
        }
        assert [p["periodo"] for p in periodos_luz] == ["04/2026", "03/2026"]
        assert fatura_abril is not None
        assert fatura_abril["debitos"][0]["PIX"] == "pix-luz"
        assert len(abertas) == 2
        assert abertas[0].unit_id == "UC123"
        assert abertas[0].codigo_pix == "pix-luz"
        assert abertas[1].vencida is True
    finally:
        if session is not None:
            session.close()
        engine.dispose()