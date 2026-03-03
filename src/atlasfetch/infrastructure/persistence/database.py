"""
Modelos e configuração do banco de dados.
SQLite por padrão. DATABASE_URL no .env (ex.: sqlite:///atlasfetch.db).
"""

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///atlasfetch.db",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.environ.get("SQL_ECHO", "").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Consulta(Base):
    """Resumo de cada consulta à API de débitos."""

    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matricula: Mapped[str] = mapped_column(String(20), index=True)
    sequencial_responsavel: Mapped[str] = mapped_column(String(20))
    zona_ligacao: Mapped[int] = mapped_column(Integer, default=1)

    quantidade_debitos: Mapped[int] = mapped_column(Integer)
    valor_total_debitos: Mapped[float] = mapped_column(Float)
    existe_debito_vencido: Mapped[bool] = mapped_column(Boolean)

    ano_filtro: Mapped[int] = mapped_column(Integer, index=True)
    mes_filtro: Mapped[int] = mapped_column(Integer, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    debitos: Mapped[list["Debito"]] = relationship(
        back_populates="consulta", cascade="all, delete-orphan"
    )


class Debito(Base):
    """Cada fatura/débito retornado pela API. numero_aviso é único por fatura."""

    __tablename__ = "debitos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consulta_id: Mapped[int] = mapped_column(ForeignKey("consultas.id"), index=True)

    referencia: Mapped[str] = mapped_column(String(20), index=True)
    data_vencimento: Mapped[datetime] = mapped_column(DateTime)
    valor_fatura: Mapped[float] = mapped_column(Float)
    situacao_pagamento: Mapped[str] = mapped_column(String(10))
    codigo_tributo: Mapped[str] = mapped_column(String(50))
    ano_lancamento: Mapped[int] = mapped_column(Integer)
    numero_aviso: Mapped[int] = mapped_column(Integer, index=True)
    numero_emissao: Mapped[int] = mapped_column(Integer)
    zona_ligacao: Mapped[int] = mapped_column(Integer)
    status_fatura: Mapped[str] = mapped_column(String(50))
    consumo: Mapped[int] = mapped_column(Integer)
    codigo_barras_digitavel: Mapped[str] = mapped_column(String(100))
    codigo_pix: Mapped[str] = mapped_column(Text)
    contrato_encerrado: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    consulta: Mapped["Consulta"] = relationship(back_populates="debitos")


class GmailOAuthConfig(Base):
    """Armazena credentials.json e token.json do Gmail OAuth (2FA)."""

    __tablename__ = "gmail_oauth_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credentials_json: Mapped[str] = mapped_column(Text, nullable=True)
    token_json: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AmazonasEnergiaToken(Base):
    """Token da API Pigz para Amazonas Energia (luz). Obtido via login manual."""

    __tablename__ = "amazonas_energia_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auth_header: Mapped[str] = mapped_column(Text)
    unit_id: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class FaturaLuz(Base):
    """Faturas de luz (Amazonas Energia) - dados da API consumes."""

    __tablename__ = "faturas_luz"
    __table_args__ = (UniqueConstraint("unit_id", "ano", "mes", name="uq_faturas_luz_unit_ano_mes"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[str] = mapped_column(String(20), index=True)
    ano: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db():
    """Cria as tabelas."""
    Base.metadata.create_all(engine)


def get_session():
    """Retorna nova sessão."""
    return SessionLocal()


def get_gmail_oauth_config() -> tuple[str | None, str | None]:
    """Retorna (credentials_json, token_json) do banco. (None, None) se vazio."""
    session = SessionLocal()
    try:
        row = session.query(GmailOAuthConfig).first()
        if row:
            return (row.credentials_json, row.token_json)
        return (None, None)
    finally:
        session.close()


def set_gmail_oauth_config(
    credentials_json: str | None = None,
    token_json: str | None = None,
) -> None:
    """Salva credentials e/ou token no banco."""
    session = SessionLocal()
    try:
        row = session.query(GmailOAuthConfig).first()
        if not row:
            row = GmailOAuthConfig(
                credentials_json=credentials_json or "",
                token_json=token_json or "",
            )
            session.add(row)
        else:
            if credentials_json is not None:
                row.credentials_json = credentials_json
            if token_json is not None:
                row.token_json = token_json
        session.commit()
    finally:
        session.close()


def get_amazonas_energia_token() -> tuple[str | None, str | None]:
    """Retorna (auth_header, unit_id) do banco. (None, None) se vazio."""
    session = SessionLocal()
    try:
        row = session.query(AmazonasEnergiaToken).first()
        if row:
            return (row.auth_header, row.unit_id)
        return (None, None)
    finally:
        session.close()


def set_amazonas_energia_token(auth_header: str, unit_id: str = "") -> None:
    """Salva token da Amazonas Energia no banco. unit_id pode ser vazio (usar .env)."""
    session = SessionLocal()
    try:
        row = session.query(AmazonasEnergiaToken).first()
        if not row:
            row = AmazonasEnergiaToken(auth_header=auth_header, unit_id=unit_id or "")
            session.add(row)
        else:
            row.auth_header = auth_header
            if unit_id:
                row.unit_id = unit_id
        session.commit()
    finally:
        session.close()


def salvar_fatura_luz(unit_id: str, ano: int, mes: int, data_json: str) -> None:
    """Salva ou atualiza fatura de luz. Upsert por (unit_id, ano, mes)."""
    session = SessionLocal()
    try:
        row = (
            session.query(FaturaLuz)
            .filter(
                FaturaLuz.unit_id == unit_id,
                FaturaLuz.ano == ano,
                FaturaLuz.mes == mes,
            )
            .first()
        )
        if row:
            row.data_json = data_json
        else:
            row = FaturaLuz(unit_id=unit_id, ano=ano, mes=mes, data_json=data_json)
            session.add(row)
        session.commit()
    finally:
        session.close()


def buscar_fatura_luz(ano: int, mes: int) -> dict | None:
    """Retorna fatura de luz do período. None se não existir."""
    session = SessionLocal()
    try:
        row = (
            session.query(FaturaLuz)
            .filter(FaturaLuz.ano == ano, FaturaLuz.mes == mes)
            .order_by(FaturaLuz.created_at.desc())
            .first()
        )
        if not row:
            return None
        data = json.loads(row.data_json)
        data["consultadoEm"] = row.created_at.isoformat()
        data["periodo"] = f"{mes:02d}/{ano}"
        data["ano"] = ano
        data["mes"] = mes
        return data
    finally:
        session.close()


def listar_periodos_luz() -> list[dict]:
    """Lista períodos com faturas de luz."""
    session = SessionLocal()
    try:
        rows = (
            session.query(FaturaLuz)
            .order_by(FaturaLuz.ano.desc(), FaturaLuz.mes.desc())
            .limit(50)
            .all()
        )
        seen = set()
        result = []
        for r in rows:
            key = (r.ano, r.mes)
            if key in seen:
                continue
            seen.add(key)
            try:
                d = json.loads(r.data_json)
                valor = d.get("valorTotal", d.get("valor", 0))
            except Exception:
                valor = 0
            result.append({
                "ano": r.ano,
                "mes": r.mes,
                "periodo": f"{r.mes:02d}/{r.ano}",
                "valorTotal": float(valor),
                "quantidadeDebitos": 1,
                "existeDebitoVencido": False,
            })
        return result
    finally:
        session.close()
