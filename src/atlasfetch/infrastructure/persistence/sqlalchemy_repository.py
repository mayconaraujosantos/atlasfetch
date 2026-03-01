"""Adaptador: repositório SQLAlchemy para consultas e débitos."""

from collections import defaultdict
from datetime import datetime

from atlasfetch.domain.ports.consulta_repository_port import ConsultaRepositoryPort
from atlasfetch.domain.value_objects.referencia import parse_referencia


def _parse_datetime(data_str: str) -> datetime:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now()


class SqlAlchemyConsultaRepository(ConsultaRepositoryPort):
    """Implementa ConsultaRepositoryPort usando SQLAlchemy."""

    def __init__(self, get_session):
        self._get_session = get_session

    def salvar_consulta_com_debitos(
        self,
        data: dict,
        ano: int,
        mes: int,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ):
        from atlasfetch.infrastructure.persistence.database import Consulta, Debito

        content = data.get("content", {})
        debitos_data = content.get("debitos", [])

        # Filtrar débitos que já existem (por numero_aviso)
        avisos = [d.get("numeroAviso") for d in debitos_data if d.get("numeroAviso")]
        session = self._get_session()
        try:
            existing = set()
            if avisos:
                for row in session.query(Debito.numero_aviso).filter(
                    Debito.numero_aviso.in_(avisos)
                ).all():
                    existing.add(row[0])
            debitos_data = [d for d in debitos_data if d.get("numeroAviso") not in existing]

            if not debitos_data:
                # Todos já existem - buscar última consulta e retornar (ou None)
                c = session.query(Consulta).filter(
                    Consulta.ano_filtro == ano, Consulta.mes_filtro == mes
                ).order_by(Consulta.created_at.desc()).first()
                if c:
                    session.refresh(c)
                    return c
                return None  # Nenhum dado novo, sem consulta existente

            valor_total = sum(d.get("valorFatura", 0) for d in debitos_data)
            existe_vencido = any(d.get("statusFatura") == "Atrasada" for d in debitos_data)

            consulta = Consulta(
                matricula=matricula,
                sequencial_responsavel=sequencial,
                zona_ligacao=zona_ligacao or content.get("zonaLigacao") or 1,
                quantidade_debitos=len(debitos_data),
                valor_total_debitos=valor_total,
                existe_debito_vencido=existe_vencido,
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

    def salvar_por_referencia(
        self,
        data: dict,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ) -> list:
        from atlasfetch.infrastructure.persistence.database import Consulta, Debito

        content = data.get("content", {})
        debitos_data = content.get("debitos", [])

        grupos = defaultdict(list)
        for d in debitos_data:
            ref = d.get("referencia", "")
            parsed = parse_referencia(ref)
            if parsed:
                grupos[parsed].append(d)

        if not grupos:
            return []

        session = self._get_session()
        consultas_criadas = []
        try:
            for (ano, mes), debitos_grupo in sorted(grupos.items()):
                # Filtrar débitos que já existem (por numero_aviso)
                avisos = [d.get("numeroAviso") for d in debitos_grupo if d.get("numeroAviso")]
                existing = set()
                if avisos:
                    for row in session.query(Debito.numero_aviso).filter(
                        Debito.numero_aviso.in_(avisos)
                    ).all():
                        existing.add(row[0])
                debitos_novos = [d for d in debitos_grupo if d.get("numeroAviso") not in existing]

                if not debitos_novos:
                    continue  # Todos já existem, pular grupo

                valor_total = sum(d.get("valorFatura", 0) for d in debitos_novos)
                existe_vencido = any(
                    d.get("statusFatura") == "Atrasada" for d in debitos_novos
                )

                consulta = Consulta(
                    matricula=matricula,
                    sequencial_responsavel=sequencial,
                    zona_ligacao=zona_ligacao,
                    quantidade_debitos=len(debitos_novos),
                    valor_total_debitos=valor_total,
                    existe_debito_vencido=existe_vencido,
                    ano_filtro=ano,
                    mes_filtro=mes,
                )
                session.add(consulta)
                session.flush()

                for d in debitos_novos:
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

            session.commit()
            return consultas_criadas
        finally:
            session.close()

    def buscar_ultima_consulta(self, ano: int, mes: int) -> dict | None:
        from atlasfetch.infrastructure.persistence.database import Consulta

        session = self._get_session()
        try:
            consultas = (
                session.query(Consulta)
                .filter(Consulta.ano_filtro == ano, Consulta.mes_filtro == mes)
                .order_by(Consulta.created_at.desc())
                .limit(1)
                .all()
            )
            if not consultas:
                return None

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
                "quantidadeDebitos": c.quantidade_debitos,
                "valorTotalDebitos": c.valor_total_debitos,
                "existeDebitoVencido": c.existe_debito_vencido,
                "debitos": debitos,
                "consultadoEm": c.created_at.isoformat(),
            }
        finally:
            session.close()

    def listar_periodos_disponiveis(self) -> list[dict]:
        """Lista períodos (ano/mês) com faturas. Ordenado do mais recente."""
        from atlasfetch.infrastructure.persistence.database import Consulta

        session = self._get_session()
        try:
            rows = (
                session.query(Consulta)
                .order_by(Consulta.ano_filtro.desc(), Consulta.mes_filtro.desc())
                .limit(100)
                .all()
            )
            seen = set()
            result = []
            for c in rows:
                key = (c.ano_filtro, c.mes_filtro)
                if key in seen:
                    continue
                seen.add(key)
                result.append({
                    "ano": c.ano_filtro,
                    "mes": c.mes_filtro,
                    "periodo": f"{c.mes_filtro:02d}/{c.ano_filtro}",
                    "valorTotal": float(c.valor_total_debitos),
                    "quantidadeDebitos": c.quantidade_debitos,
                    "existeDebitoVencido": c.existe_debito_vencido,
                })
                if len(result) >= 24:
                    break
            return result
        finally:
            session.close()
