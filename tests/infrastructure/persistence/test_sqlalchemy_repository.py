from pathlib import Path

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from atlasfetch.infrastructure.persistence import database as db
from atlasfetch.infrastructure.persistence.sqlalchemy_repository import SqlAlchemyConsultaRepository


def build_repository(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'tests.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.engine = engine
    db.SessionLocal = session_local
    db.Base.metadata.drop_all(bind=engine)
    db.Base.metadata.create_all(bind=engine)
    return SqlAlchemyConsultaRepository(get_session=session_local), session_local


def test_salvar_consulta_com_debitos_persiste_apenas_novos(tmp_path):
    repository, session_local = build_repository(tmp_path)
    payload = {
        "content": {
            "debitos": [
                {
                    "referencia": "03/2026",
                    "dataVencimento": "2026-03-10T00:00:00Z",
                    "valorFatura": 10.0,
                    "situacaoPagamento": "D",
                    "codigoTributo": "123",
                    "anoLancamento": 2026,
                    "numeroAviso": 1001,
                    "numeroEmissao": 1,
                    "zonaLigacao": 1,
                    "statusFatura": "Atrasada",
                    "consumo": 20,
                    "codigoBarrasDigitavel": "123456",
                    "codigoPIX": "pix-1",
                    "contratoEncerrado": False,
                },
                {
                    "referencia": "03/2026",
                    "dataVencimento": "2026-03-11T00:00:00Z",
                    "valorFatura": 15.0,
                    "situacaoPagamento": "P",
                    "codigoTributo": "456",
                    "anoLancamento": 2026,
                    "numeroAviso": 1002,
                    "numeroEmissao": 2,
                    "zonaLigacao": 1,
                    "statusFatura": "Em Aberto",
                    "consumo": 30,
                    "codigoBarrasDigitavel": "654321",
                    "codigoPIX": "pix-2",
                    "contratoEncerrado": False,
                },
            ]
        }
    }

    consulta = repository.salvar_consulta_com_debitos(
        payload,
        ano=2026,
        mes=3,
        matricula="matricula-1",
        sequencial="seq-1",
    )
    segunda_consulta = repository.salvar_consulta_com_debitos(
        payload,
        ano=2026,
        mes=3,
        matricula="matricula-1",
        sequencial="seq-1",
    )

    session = session_local()
    try:
        assert consulta is not None
        assert segunda_consulta is not None
        assert session.query(db.Consulta).count() == 1
        assert session.query(db.Debito).count() == 2
        assert consulta.quantidade_debitos == 2
        assert consulta.valor_total_debitos == pytest.approx(25.0)
        assert consulta.existe_debito_vencido is True
        assert segunda_consulta.id == consulta.id
    finally:
        session.close()


def test_salvar_por_referencia_agrupa_por_mes_e_ano(tmp_path):
    repository, session_local = build_repository(tmp_path)
    payload = {
        "content": {
            "debitos": [
                {
                    "referencia": "03/2026",
                    "dataVencimento": "2026-03-10T00:00:00Z",
                    "valorFatura": 10.0,
                    "numeroAviso": 2001,
                    "statusFatura": "Em Aberto",
                },
                {
                    "referencia": "02/2026",
                    "dataVencimento": "2026-02-10T00:00:00Z",
                    "valorFatura": 15.0,
                    "numeroAviso": 2002,
                    "statusFatura": "Atrasada",
                },
                {
                    "referencia": "invalida",
                    "dataVencimento": "2026-01-10T00:00:00Z",
                    "valorFatura": 20.0,
                    "numeroAviso": 2003,
                    "statusFatura": "Em Aberto",
                },
            ]
        }
    }

    consultas = repository.salvar_por_referencia(
        payload,
        matricula="matricula-1",
        sequencial="seq-1",
        zona_ligacao=1,
    )
    periodos = repository.listar_periodos_disponiveis()
    ultima = repository.buscar_ultima_consulta(2026, 3)

    session = session_local()
    try:
        assert len(consultas) == 2
        assert session.query(db.Consulta).count() == 2
        assert session.query(db.Debito).count() == 2
        assert [p["periodo"] for p in periodos] == ["03/2026", "02/2026"]
        assert ultima is not None
        assert ultima["quantidadeDebitos"] == 1
        assert ultima["valorTotalDebitos"] == pytest.approx(10.0)
    finally:
        session.close()