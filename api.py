"""
API REST para consulta de faturas por data.
"""

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from database import Debito, Consulta, init_db, get_session
from scraper import login, fetch_debito_totais

load_dotenv()

app = FastAPI(title="Atlasfetch API", description="API de faturas Águas de Manaus")


# Schemas
class DebitoOut(BaseModel):
    referencia: str
    dataVencimento: str
    valorFatura: float
    situacaoPagamento: str
    codigoTributo: str
    anoLancamento: int
    numeroAviso: int
    numeroEmissao: int
    zonaLigacao: int
    statusFatura: str
    consumo: int
    codigoBarrasDigitavel: str
    codigoPIX: str
    contratoEncerrado: bool


class FaturasResponse(BaseModel):
    conteudo: dict[str, Any]


def _parse_datetime(data_str: str) -> datetime:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now()


def _save_to_db(data: dict, ano: int, mes: int, matricula: str = "", sequencial: str = "") -> Consulta:
    """Salva resposta da API no banco."""
    content = data.get("content", {})
    debitos_data = content.get("debitos", [])

    session = get_session()
    try:
        consulta = Consulta(
            matricula=matricula or os.environ.get("AGUAS_MATRICULA", ""),
            sequencial_responsavel=sequencial or os.environ.get("AGUAS_SEQUENCIAL", ""),
            zona_ligacao=content.get("zonaLigacao") or 1,
            quantidade_debitos=content.get("quantidadeDebitos", 0),
            valor_total_debitos=content.get("valorTotalDebitos", 0),
            existe_debito_vencido=content.get("existeDebitoVencido", False),
            ano_filtro=ano,
            mes_filtro=mes,
        )
        session.add(consulta)
        session.flush()

        for d in debitos_data:
            debito = Debito(
                consulta_id=consulta.id,
                referencia=d.get("referencia", ""),
                data_vencimento=_parse_datetime(d.get("dataVencimento", "")),
                valor_fatura=d.get("valorFatura", 0),
                situacao_pagamento=d.get("situacaoPagamento", ""),
                codigo_tributo=d.get("codigoTributo", ""),
                ano_lancamento=d.get("anoLancamento", 0),
                numero_aviso=d.get("numeroAviso", 0),
                numero_emissao=d.get("numeroEmissao", 0),
                zona_ligacao=d.get("zonaLigacao", 0),
                status_fatura=d.get("statusFatura", ""),
                consumo=d.get("consumo", 0),
                codigo_barras_digitavel=d.get("codigoBarrasDigitavel", ""),
                codigo_pix=d.get("codigoPIX", ""),
                contrato_encerrado=d.get("contratoEncerrado", False),
            )
            session.add(debito)

        session.commit()
        session.refresh(consulta)
        return consulta
    finally:
        session.close()


@app.on_event("startup")
def startup():
    init_db()
    try:
        from scheduler import start_scheduler
        start_scheduler()
    except ImportError:
        pass


@app.on_event("shutdown")
def shutdown():
    try:
        from scheduler import stop_scheduler
        stop_scheduler()
    except ImportError:
        pass


@app.get("/api/faturas/{ano}/{mes}")
@app.get("/api/faturas/{ano}/{mes}/{dia}")
async def get_faturas(
    ano: int,
    mes: int,
    dia: int | None = None,
    client_id: str | None = Query(None, description="ID do cliente (futuro multi-tenant)"),
):
    """
    Consulta faturas por data (ano/mês/dia).
    Faz login, busca dados na API Aegea, salva no banco e retorna.
    """
    if not ano or not mes:
        raise HTTPException(400, "ano e mes são obrigatórios")
    if mes < 1 or mes > 12:
        raise HTTPException(400, "mes deve estar entre 1 e 12")

    cpf = os.environ.get("AGUAS_CPF")
    senha = os.environ.get("AGUAS_SENHA")
    matricula = os.environ.get("AGUAS_MATRICULA")
    sequencial = os.environ.get("AGUAS_SEQUENCIAL")
    zona = os.environ.get("AGUAS_ZONA", "1")

    if not cpf or not senha:
        raise HTTPException(500, "AGUAS_CPF e AGUAS_SENHA não configurados")

    if not matricula or not sequencial:
        raise HTTPException(500, "AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")

    try:
        # Login e obtenção do token
        result = login(cpf=cpf, senha=senha, headless=True)

        # Usar matrícula do login se não estiver no .env
        mat = matricula or result.matricula
        seq = sequencial or result.sequencial_responsavel
        zon = zona or (result.zona_ligacao or "1")

        if not mat or not seq:
            raise HTTPException(500, "Matrícula/sequencial não obtidos. Configure AGUAS_MATRICULA e AGUAS_SEQUENCIAL")

        # Buscar débitos
        data = fetch_debito_totais(
            access_token=result.access_token,
            matricula=mat,
            sequencial_responsavel=seq,
            zona_ligacao=zon,
        )

        # Salvar no banco
        _save_to_db(data, ano, mes, matricula=mat, sequencial=seq)

        # Filtrar por mês/ano se necessário (a API retorna todos, filtramos por referencia)
        content = data.get("content", {})
        debitos = content.get("debitos", [])

        if ano or mes:
            debitos_filtrados = [
                d for d in debitos
                if _ref_match(d.get("referencia", ""), ano, mes)
            ]
            content = {**content, "debitos": debitos_filtrados}

        return {"content": content}
    except Exception as e:
        raise HTTPException(500, str(e))


def _ref_match(referencia: str, ano: int, mes: int) -> bool:
    """Verifica se referencia (ex: 01/2026) corresponde ao ano/mês."""
    try:
        parts = referencia.split("/")
        if len(parts) == 2:
            ref_mes = int(parts[0])
            ref_ano = int(parts[1])
            return ref_mes == mes and ref_ano == ano
    except (ValueError, IndexError):
        pass
    return True


@app.get("/api/faturas/{ano}/{mes}/historico")
async def get_faturas_historico(ano: int, mes: int):
    """Retorna faturas já salvas no banco (sem fazer nova consulta)."""
    session = get_session()
    try:
        consultas = (
            session.query(Consulta)
            .filter(Consulta.ano_filtro == ano, Consulta.mes_filtro == mes)
            .order_by(Consulta.created_at.desc())
            .limit(1)
            .all()
        )
        if not consultas:
            raise HTTPException(404, "Nenhuma consulta encontrada para esta data")

        c = consultas[0]
        debitos = [
            {
                "referencia": d.referencia,
                "dataVencimento": d.data_vencimento.isoformat(),
                "valorFatura": d.valor_fatura,
                "situacaoPagamento": d.situacao_pagamento,
                "codigoTributo": d.codigo_tributo,
                "anoLancamento": d.ano_lancamento,
                "numeroAviso": d.numero_aviso,
                "numeroEmissao": d.numero_emissao,
                "zonaLigacao": d.zona_ligacao,
                "statusFatura": d.status_fatura,
                "consumo": d.consumo,
                "codigoBarrasDigitavel": d.codigo_barras_digitavel,
                "codigoPIX": d.codigo_pix,
                "contratoEncerrado": d.contrato_encerrado,
            }
            for d in c.debitos
        ]
        return {
            "content": {
                "quantidadeDebitos": c.quantidade_debitos,
                "valorTotalDebitos": c.valor_total_debitos,
                "existeDebitoVencido": c.existe_debito_vencido,
                "debitos": debitos,
                "tenantUnidade": None,
                "unidade": None,
                "consultadoEm": c.created_at.isoformat(),
            }
        }
    finally:
        session.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/sync/run")
async def run_sync_now():
    """Executa o job de sincronização imediatamente (útil para testes)."""
    try:
        from sync_job import run_sync_job
        result = run_sync_job()
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
