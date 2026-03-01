"""
Modelos e configuração do banco de dados.
PostgreSQL por padrão. DATABASE_URL no .env.
"""

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
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/atlasfetch",
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
