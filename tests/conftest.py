import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atlasfetch.api.app import app
from atlasfetch.api.routes import faturas
from atlasfetch.infrastructure.persistence import database as db
from atlasfetch.infrastructure.persistence.sqlalchemy_repository import SqlAlchemyConsultaRepository


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sqlite_test_db(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test-suite.db'}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", session_local)
    monkeypatch.setattr(db, "init_db", lambda: db.Base.metadata.create_all(bind=engine))

    db.Base.metadata.create_all(bind=engine)
    yield session_local
    db.Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def integration_client(monkeypatch, sqlite_test_db):
    monkeypatch.setattr(
        faturas,
        "get_repository",
        lambda: SqlAlchemyConsultaRepository(get_session=sqlite_test_db),
    )
    with TestClient(app) as client:
        yield client