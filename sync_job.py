"""
Job de sincronização: executa scraper e salva débitos no banco.
Agrupa por referencia (MM/YYYY) - uma Consulta por mês/ano.
"""

import logging
import os
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv

from database import Debito, Consulta, init_db, get_session
from scraper import login, fetch_debito_totais

load_dotenv()

logger = logging.getLogger(__name__)


def _parse_datetime(data_str: str) -> datetime:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now()


def _parse_referencia(referencia: str) -> tuple[int, int] | None:
    """Extrai (ano, mes) de referencia no formato MM/YYYY. Retorna None se inválido."""
    try:
        parts = referencia.strip().split("/")
        if len(parts) == 2:
            mes = int(parts[0])
            ano = int(parts[1])
            if 1 <= mes <= 12 and ano > 2000:
                return (ano, mes)
    except (ValueError, IndexError):
        pass
    return None


def save_debitos_by_referencia(
    data: dict,
    matricula: str = "",
    sequencial: str = "",
    zona_ligacao: int = 1,
) -> list[Consulta]:
    """
    Salva débitos agrupados por referencia (MM/YYYY).
    Cria uma Consulta por mês/ano com seus débitos.
    """
    content = data.get("content", {})
    debitos_data = content.get("debitos", [])

    # Agrupar por (ano, mes)
    grupos: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for d in debitos_data:
        ref = d.get("referencia", "")
        parsed = _parse_referencia(ref)
        if parsed:
            grupos[parsed].append(d)

    if not grupos:
        logger.warning("Nenhum débito com referencia válida (MM/YYYY)")
        return []

    matricula = matricula or os.environ.get("AGUAS_MATRICULA", "")
    sequencial = sequencial or os.environ.get("AGUAS_SEQUENCIAL", "")

    session = get_session()
    consultas_criadas = []
    try:
        for (ano, mes), debitos_grupo in sorted(grupos.items()):
            valor_total = sum(d.get("valorFatura", 0) for d in debitos_grupo)
            existe_vencido = any(
                d.get("statusFatura") == "Atrasada" for d in debitos_grupo
            )

            consulta = Consulta(
                matricula=matricula,
                sequencial_responsavel=sequencial,
                zona_ligacao=zona_ligacao,
                quantidade_debitos=len(debitos_grupo),
                valor_total_debitos=valor_total,
                existe_debito_vencido=existe_vencido,
                ano_filtro=ano,
                mes_filtro=mes,
            )
            session.add(consulta)
            session.flush()

            for d in debitos_grupo:
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

            session.refresh(consulta)
            consultas_criadas.append(consulta)
            logger.info(
                "Salvo: referencia %02d/%d - %d débito(s), R$ %.2f",
                mes, ano, len(debitos_grupo), valor_total,
            )

        session.commit()
        return consultas_criadas
    finally:
        session.close()


def run_sync_job() -> dict:
    """
    Executa login, busca débitos na API Aegea e salva no banco por referencia.
    Retorna dict com status e quantidade de consultas salvas.
    """
    cpf = os.environ.get("AGUAS_CPF")
    senha = os.environ.get("AGUAS_SENHA")
    matricula = os.environ.get("AGUAS_MATRICULA")
    sequencial = os.environ.get("AGUAS_SEQUENCIAL")
    zona = os.environ.get("AGUAS_ZONA", "1")

    if not cpf or not senha:
        raise ValueError("AGUAS_CPF e AGUAS_SENHA não configurados")
    if not matricula or not sequencial:
        raise ValueError("AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")

    logger.info("Iniciando job de sincronização agendada")
    result = login(cpf=cpf, senha=senha, headless=True)

    mat = matricula or result.matricula
    seq = sequencial or result.sequencial_responsavel
    zon = zona or (result.zona_ligacao or "1")

    if not mat or not seq:
        raise ValueError("Matrícula/sequencial não obtidos")

    data = fetch_debito_totais(
        access_token=result.access_token,
        matricula=mat,
        sequencial_responsavel=seq,
        zona_ligacao=zon,
    )

    consultas = save_debitos_by_referencia(
        data, matricula=mat, sequencial=seq, zona_ligacao=int(zon) if zon else 1
    )

    logger.info("Job concluído: %d consulta(s) salva(s)", len(consultas))
    return {"status": "ok", "consultas_salvas": len(consultas)}
