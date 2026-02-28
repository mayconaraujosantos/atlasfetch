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
        from database import Consulta, Debito

        content = data.get("content", {})
        debitos_data = content.get("debitos", [])

        session = self._get_session()
        try:
            consulta = Consulta(
                matricula=matricula,
                sequencial_responsavel=sequencial,
                zona_ligacao=zona_ligacao or content.get("zonaLigacao") or 1,
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

    def salvar_por_referencia(
        self,
        data: dict,
        matricula: str,
        sequencial: str,
        zona_ligacao: int = 1,
    ) -> list:
        from database import Consulta, Debito

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

            session.commit()
            return consultas_criadas
        finally:
            session.close()

    def buscar_ultima_consulta(self, ano: int, mes: int) -> dict | None:
        from database import Consulta

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
