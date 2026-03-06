"""
Modelos e configuração do banco de dados.
SQLite por padrão. DATABASE_URL no .env (ex.: sqlite:///atlasfetch.db).
"""

import json
import os
import re
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


class FaturaLuzAberta(Base):
    """Faturas abertas da Amazonas Energia (payload novo da agência)."""

    __tablename__ = "faturas_luz_abertas"
    __table_args__ = (
        UniqueConstraint("unit_id", "id_boleto", name="uq_faturas_luz_abertas_unit_boleto"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[str] = mapped_column(String(20), index=True)
    ano: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)
    mes_ano_referencia: Mapped[str | None] = mapped_column(String(7), index=True, nullable=True)
    data_vencimento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    valor_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    id_boleto: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    boleto: Mapped[str | None] = mapped_column(Text, nullable=True)
    codigo_barras: Mapped[str | None] = mapped_column(Text, nullable=True)
    codigo_pix: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_ame: Mapped[str | None] = mapped_column(String(50), nullable=True)
    situacao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    descricao_situacao: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vencida: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FaturaEscola(Base):
    """
    Parcelas escolares (Educação Adventista 7edu).
    Campos: id, nome_aluno, ano, mes, created_at, valor, data_validade_pix, status_pix, qrcode_base64, codigo_pix.
    Sem duplicidade de aluno: usamos apenas nome_aluno.
    """

    __tablename__ = "faturas_escola"
    __table_args__ = (
        UniqueConstraint("nome_aluno", "ano", "mes", name="uq_faturas_escola_aluno_ano_mes"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_aluno: Mapped[str] = mapped_column(String(200), index=True)
    ano: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_validade_pix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_pix: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ativo | expirado
    qrcode_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    codigo_pix: Mapped[str | None] = mapped_column(Text, nullable=True)


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


def _parse_mes_ano_ref(ref: str | None) -> tuple[int, int] | None:
    """Converte referência MM/YYYY para (ano, mes)."""
    if not ref:
        return None
    m = re.search(r"(\d{1,2})[/\-](\d{4})", str(ref))
    if not m:
        return None
    mes, ano = int(m.group(1)), int(m.group(2))
    if 1 <= mes <= 12 and ano > 2000:
        return (ano, mes)
    return None


def salvar_fatura_luz_aberta(unit_id: str, debito: dict) -> None:
    """Salva/atualiza uma fatura aberta da Amazonas Energia (payload novo)."""
    if not isinstance(debito, dict):
        return
    ref = debito.get("MES_ANO_REFERENCIA") or debito.get("mes_ano_referencia") or debito.get("referencia")
    parsed = _parse_mes_ano_ref(str(ref)) if ref else None
    if not parsed:
        return
    ano, mes = parsed
    id_boleto = debito.get("ID_BOLETO")
    try:
        id_boleto = int(id_boleto) if id_boleto is not None else None
    except Exception:
        id_boleto = None
    numero_ame = str(debito.get("NUMERO_AME") or "").strip() or None
    session = SessionLocal()
    try:
        q = session.query(FaturaLuzAberta).filter(FaturaLuzAberta.unit_id == str(unit_id))
        row = None
        if id_boleto is not None:
            row = q.filter(FaturaLuzAberta.id_boleto == id_boleto).first()
        elif numero_ame:
            row = q.filter(
                FaturaLuzAberta.ano == ano,
                FaturaLuzAberta.mes == mes,
                FaturaLuzAberta.numero_ame == numero_ame,
            ).first()

        if not row:
            row = FaturaLuzAberta(
                unit_id=str(unit_id),
                ano=ano,
                mes=mes,
                mes_ano_referencia=f"{mes:02d}/{ano}",
                id_boleto=id_boleto,
                numero_ame=numero_ame,
                payload_json=json.dumps(debito, ensure_ascii=False),
            )
            session.add(row)

        row.data_vencimento = str(debito.get("DATA_VENCIMENTO") or "")
        row.valor_total = float(debito.get("VALOR_TOTAL") or 0)
        row.boleto = str(debito.get("BOLETO") or "")
        row.codigo_barras = str(debito.get("CODIGO_BARRAS") or "")
        row.codigo_pix = str(debito.get("PIX") or "")
        row.situacao = str(debito.get("SITUACAO") or "")
        row.descricao_situacao = str(debito.get("DESCRICAO_SITUACAO") or "")
        vencida = debito.get("VENCIDA")
        row.vencida = bool(vencida) if vencida is not None else None
        row.payload_json = json.dumps(debito, ensure_ascii=False)
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


def _status_pix_from_validade(data_validade: str | None) -> str:
    """Retorna 'ativo' ou 'expirado' baseado na data de validade do PIX."""
    if not data_validade or not isinstance(data_validade, str):
        return "ativo"
    try:
        # Formato: "05/03/2026 às 02:34" ou "05/03/2026 02:34"
        m = re.search(
            r"(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:às\s*)?(\d{1,2}):(\d{2})?",
            data_validade.strip(),
        )
        if m:
            dia, mes, ano, h, minu = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5) or 0)
            from datetime import datetime as dt
            validade = dt(ano, mes, dia, h, minu)
            return "expirado" if validade < dt.now() else "ativo"
    except Exception:
        pass
    return "ativo"


def salvar_fatura_escola(
    nome_aluno: str,
    ano: int,
    mes: int,
    *,
    valor: float | None = None,
    data_validade_pix: str | None = None,
    codigo_pix: str | None = None,
    qrcode_base64: str | None = None,
) -> None:
    """Salva ou atualiza parcela escolar. Upsert por (nome_aluno, ano, mes)."""
    nome_aluno = (nome_aluno or "").strip() or "aluno_sem_nome"
    status_pix = _status_pix_from_validade(data_validade_pix) if data_validade_pix else None
    session = SessionLocal()
    try:
        row = (
            session.query(FaturaEscola)
            .filter(
                FaturaEscola.nome_aluno == nome_aluno,
                FaturaEscola.ano == ano,
                FaturaEscola.mes == mes,
            )
            .first()
        )
        if row:
            if valor is not None:
                row.valor = valor
            if data_validade_pix is not None:
                row.data_validade_pix = data_validade_pix
                row.status_pix = _status_pix_from_validade(data_validade_pix)
            if codigo_pix is not None:
                row.codigo_pix = codigo_pix
            if qrcode_base64 is not None:
                row.qrcode_base64 = qrcode_base64
        else:
            row = FaturaEscola(
                nome_aluno=nome_aluno,
                ano=ano,
                mes=mes,
                valor=valor,
                data_validade_pix=data_validade_pix,
                status_pix=status_pix,
                codigo_pix=codigo_pix,
                qrcode_base64=qrcode_base64,
            )
            session.add(row)
        session.commit()
    finally:
        session.close()


def buscar_fatura_escola(ano: int, mes: int) -> dict | None:
    """Retorna parcelas escolares do período. Agrupa por período."""
    session = SessionLocal()
    try:
        rows = (
            session.query(FaturaEscola)
            .filter(FaturaEscola.ano == ano, FaturaEscola.mes == mes)
            .order_by(FaturaEscola.created_at.desc())
            .all()
        )
        if not rows:
            return None
        debitos = []
        valor_total = 0.0
        for r in rows:
            valor = float(r.valor if r.valor is not None else 0)
            valor_total += valor
            status_pix = r.status_pix or _status_pix_from_validade(r.data_validade_pix or "")
            situacao = "D" if status_pix == "expirado" else "P"
            debitos.append({
                "id": r.id,
                "referencia": f"{r.mes:02d}/{r.ano}",
                "valorFatura": valor,
                "dataVencimento": r.data_validade_pix or "",
                "codigoBarrasDigitavel": "",
                "codigoPIX": r.codigo_pix or "",
                "codigoPix": r.codigo_pix or "",
                "dataValidadePix": r.data_validade_pix or "",
                "statusPix": status_pix,
                "qrcodeBase64": r.qrcode_base64 or "",
                "statusFatura": "Pago" if situacao == "P" else "Em Aberto",
                "situacaoPagamento": situacao,
                "BeneficiaryName": r.nome_aluno or "",
            })
        return {
            "valorTotalDebitos": valor_total,
            "quantidadeDebitos": len(debitos),
            "existeDebitoVencido": any(d["situacaoPagamento"] == "D" for d in debitos),
            "consultadoEm": rows[0].created_at.isoformat(),
            "debitos": debitos,
            "periodo": f"{mes:02d}/{ano}",
            "ano": ano,
            "mes": mes,
        }
    finally:
        session.close()


def listar_faturas_escola(
    *,
    ano: int | None = None,
    mes: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """Lista faturas escolares com campos PIX (opcionalmente filtrando por ano/mês)."""
    session = SessionLocal()
    try:
        q = session.query(FaturaEscola)
        if ano is not None:
            q = q.filter(FaturaEscola.ano == ano)
        if mes is not None:
            q = q.filter(FaturaEscola.mes == mes)
        rows = (
            q.order_by(FaturaEscola.ano.desc(), FaturaEscola.mes.desc(), FaturaEscola.created_at.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
        result = []
        for r in rows:
            result.append(
                {
                    "id": r.id,
                    "nome_aluno": r.nome_aluno or "",
                    "ano": r.ano,
                    "mes": r.mes,
                    "valor": float(r.valor if r.valor is not None else 0),
                    "dataValidadePix": r.data_validade_pix or "",
                    "statusPix": r.status_pix or _status_pix_from_validade(r.data_validade_pix or ""),
                    "codigoPix": r.codigo_pix or "",
                    "qrcodeBase64": r.qrcode_base64 or "",
                    "createdAt": r.created_at.isoformat() if r.created_at else "",
                }
            )
        return result
    finally:
        session.close()


def listar_periodos_escola() -> list[dict]:
    """Lista períodos com parcelas escolares."""
    session = SessionLocal()
    try:
        rows = (
            session.query(FaturaEscola)
            .order_by(FaturaEscola.ano.desc(), FaturaEscola.mes.desc())
            .limit(200)
            .all()
        )
        # Agrupar por (ano, mes)
        agg: dict[tuple[int, int], list[float]] = {}
        for r in rows:
            key = (r.ano, r.mes)
            val = float(r.valor if r.valor is not None else 0)
            agg.setdefault(key, []).append(val)
        result = [
            {
                "ano": ano,
                "mes": mes,
                "periodo": f"{mes:02d}/{ano}",
                "valorTotal": sum(vals),
                "quantidadeDebitos": len(vals),
                "existeDebitoVencido": False,
            }
            for (ano, mes), vals in sorted(agg.items(), key=lambda x: (-x[0][0], -x[0][1]))
        ]
        return result[:50]
    finally:
        session.close()
