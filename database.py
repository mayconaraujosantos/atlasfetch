"""
Modelos e configuração do banco de dados.
"""

from datetime import datetime

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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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

    ano_filtro: Mapped[int] = mapped_column(Integer, index=True)  # ano da requisição
    mes_filtro: Mapped[int] = mapped_column(Integer, index=True)  # mês da requisição

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    debitos: Mapped[list["Debito"]] = relationship(back_populates="consulta", cascade="all, delete-orphan")


class Debito(Base):
    """Cada fatura/débito retornado pela API."""

    __tablename__ = "debitos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consulta_id: Mapped[int] = mapped_column(ForeignKey("consultas.id"), index=True)

    referencia: Mapped[str] = mapped_column(String(20), index=True)  # "01/2026"
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


# SQLite por padrão, DATABASE_URL no .env para PostgreSQL
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./atlasfetch.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.environ.get("SQL_ECHO", "").lower() == "true",
)

from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Cria as tabelas."""
    Base.metadata.create_all(engine)


def get_session():
    """Retorna nova sessão."""
    return SessionLocal()
