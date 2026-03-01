"""
Rotas de faturas - formato otimizado para app mobile (React Native).

Endpoints:
- GET /api/faturas           → lista períodos disponíveis
- GET /api/faturas/{ano}/{mes} → detalhes (resumo + débitos com valor, data, códigos)
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from atlasfetch.api.container import get_config, get_repository, _create_buscar_faturas

router = APIRouter(prefix="/api/faturas", tags=["faturas"])


class PeriodoSchema(BaseModel):
    ano: int
    mes: int
    periodo: str
    valorTotal: float
    quantidadeDebitos: int
    existeDebitoVencido: bool


class ListaPeriodosResponse(BaseModel):
    periodos: list[PeriodoSchema]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "periodos": [
                        {
                            "ano": 2026,
                            "mes": 2,
                            "periodo": "02/2026",
                            "valorTotal": 62.57,
                            "quantidadeDebitos": 1,
                            "existeDebitoVencido": False,
                        },
                        {
                            "ano": 2026,
                            "mes": 1,
                            "periodo": "01/2026",
                            "valorTotal": 62.61,
                            "quantidadeDebitos": 1,
                            "existeDebitoVencido": True,
                        },
                    ]
                }
            ]
        }
    }


class DebitoSchema(BaseModel):
    id: int | None
    referencia: str
    valor: float
    dataVencimento: str
    codigoBarras: str
    codigoPix: str
    status: str
    situacaoPagamento: str


class ResumoSchema(BaseModel):
    periodo: str
    ano: int
    mes: int
    valorTotal: float
    quantidadeDebitos: int
    existeDebitoVencido: bool
    consultadoEm: str


class FaturaResponse(BaseModel):
    resumo: ResumoSchema
    debitos: list[DebitoSchema]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resumo": {
                        "periodo": "02/2026",
                        "ano": 2026,
                        "mes": 2,
                        "valorTotal": 62.57,
                        "quantidadeDebitos": 1,
                        "existeDebitoVencido": False,
                        "consultadoEm": "2026-02-28T22:46:26",
                    },
                    "debitos": [
                        {
                            "id": 160408916,
                            "referencia": "02/2026",
                            "valor": 62.57,
                            "dataVencimento": "2026-03-02T03:00:00",
                            "codigoBarras": "8265000000036257...",
                            "codigoPix": "00020126870014br.gov.bcb.pix...",
                            "status": "Em Aberto",
                            "situacaoPagamento": "D",
                        }
                    ],
                }
            ]
        }
    }


def _formatar_debito_mobile(d: dict) -> dict:
    """Formata débito para consumo no app (valor, data, codigoBarras, codigoPix)."""
    num = d.get("numeroAviso")
    return {
        "id": num if num else None,
        "referencia": d.get("referencia", ""),
        "valor": float(d.get("valorFatura", 0)),
        "dataVencimento": str(d.get("dataVencimento", "")),
        "codigoBarras": d.get("codigoBarrasDigitavel", ""),
        "codigoPix": d.get("codigoPIX", ""),
        "status": d.get("statusFatura", ""),
        "situacaoPagamento": d.get("situacaoPagamento", ""),
    }


@router.get(
    "",
    response_model=ListaPeriodosResponse,
    responses={
        200: {
            "description": "Lista de períodos com faturas",
            "content": {
                "application/json": {
                    "example": {
                        "periodos": [
                            {
                                "ano": 2026,
                                "mes": 2,
                                "periodo": "02/2026",
                                "valorTotal": 62.57,
                                "quantidadeDebitos": 1,
                                "existeDebitoVencido": False,
                            },
                            {
                                "ano": 2026,
                                "mes": 1,
                                "periodo": "01/2026",
                                "valorTotal": 62.61,
                                "quantidadeDebitos": 1,
                                "existeDebitoVencido": True,
                            },
                        ]
                    }
                }
            },
        }
    },
)
async def listar_periodos():
    """
    Lista períodos com faturas disponíveis.
    Para o app exibir: "Você tem faturas de 12/2025, 01/2026..."
    """
    repository = get_repository()
    periodos = repository.listar_periodos_disponiveis()
    return {"periodos": periodos}


@router.get(
    "/{ano}/{mes}",
    response_model=FaturaResponse,
    responses={
        200: {
            "description": "Fatura com resumo e débitos",
            "content": {
                "application/json": {
                    "example": {
                        "resumo": {
                            "periodo": "02/2026",
                            "ano": 2026,
                            "mes": 2,
                            "valorTotal": 62.57,
                            "quantidadeDebitos": 1,
                            "existeDebitoVencido": False,
                            "consultadoEm": "2026-02-28T22:46:26",
                        },
                        "debitos": [
                            {
                                "id": 160408916,
                                "referencia": "02/2026",
                                "valor": 62.57,
                                "dataVencimento": "2026-03-02T03:00:00",
                                "codigoBarras": "8265000000036257...",
                                "codigoPix": "00020126870014br.gov.bcb.pix...",
                                "status": "Em Aberto",
                                "situacaoPagamento": "D",
                            }
                        ],
                    }
                }
            },
        },
        404: {"description": "Nenhuma fatura encontrada para este período"},
        400: {"description": "Parâmetros inválidos"},
    },
)
async def get_fatura(
    ano: int = Path(..., description="Ano da fatura (ex: 2026)"),
    mes: int = Path(..., ge=1, le=12, description="Mês da fatura (1 a 12)"),
    atualizar: bool = Query(
        False,
        description="Se true, força nova consulta à API (login + busca)",
    ),
):
    """
    Retorna fatura de um período (ano/mês).

    - **atualizar=false** (padrão): lê do banco (rápido)
    - **atualizar=true**: faz login, busca na API Aegea, salva e retorna

    Cada débito inclui: valor, dataVencimento, codigoBarras, codigoPix, status.
    """
    repository = get_repository()

    if atualizar:
        config = get_config()
        if not config["cpf"] or not config["senha"]:
            raise HTTPException(500, "AGUAS_CPF e AGUAS_SENHA não configurados")
        if not config["matricula"] or not config["sequencial"]:
            raise HTTPException(500, "AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")
        try:
            use_case = _create_buscar_faturas()
            raw = use_case.execute(
                ano=ano,
                mes=mes,
                cpf=config["cpf"],
                senha=config["senha"],
                matricula=config["matricula"],
                sequencial=config["sequencial"],
                zona=config["zona"],
            )
            content = raw.get("content", {})
            debitos_raw = content.get("debitos", [])
            if "valorTotalDebitos" not in content:
                content["valorTotalDebitos"] = sum(d.get("valorFatura", 0) for d in debitos_raw)
            if "quantidadeDebitos" not in content:
                content["quantidadeDebitos"] = len(debitos_raw)
            if "existeDebitoVencido" not in content:
                content["existeDebitoVencido"] = any(
                    d.get("statusFatura") == "Atrasada" for d in debitos_raw
                )
            if "consultadoEm" not in content:
                content["consultadoEm"] = datetime.utcnow().isoformat()
        except ValueError as e:
            raise HTTPException(500, str(e))
        except Exception as e:
            raise HTTPException(500, str(e))
    else:
        result = repository.buscar_ultima_consulta(ano, mes)
        if not result:
            raise HTTPException(404, "Nenhuma fatura encontrada para este período")
        debitos_raw = result.get("debitos", [])
        content = result

    debitos = [_formatar_debito_mobile(d) for d in debitos_raw]

    return {
        "resumo": {
            "periodo": f"{mes:02d}/{ano}",
            "ano": ano,
            "mes": mes,
            "valorTotal": float(content.get("valorTotalDebitos", 0)),
            "quantidadeDebitos": content.get("quantidadeDebitos", 0),
            "existeDebitoVencido": content.get("existeDebitoVencido", False),
            "consultadoEm": content.get("consultadoEm", ""),
        },
        "debitos": debitos,
    }


# Compatibilidade: rota antiga redireciona para a nova
@router.get("/{ano}/{mes}/historico", include_in_schema=False)
async def get_faturas_historico_legado(ano: int, mes: int):
    """Legado: retorna formato antigo. Use GET /api/faturas/{ano}/{mes}."""
    repository = get_repository()
    result = repository.buscar_ultima_consulta(ano, mes)
    if not result:
        raise HTTPException(404, "Nenhuma consulta encontrada para esta data")
    return {
        "content": {
            **result,
            "tenantUnidade": None,
            "unidade": None,
        }
    }
