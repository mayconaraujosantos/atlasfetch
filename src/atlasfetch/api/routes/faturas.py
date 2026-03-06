"""
Rotas de faturas - formato otimizado para app mobile e consumo por IA.

Endpoints:
- GET /api/faturas?provedor=aguas|luz|todos  → lista períodos
- GET /api/faturas/{ano}/{mes}?provedor=aguas|luz  → detalhes

Para IA: "conta de luz do mês 2" → GET /api/faturas?provedor=luz + GET /api/faturas/2026/2?provedor=luz
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from atlasfetch.api.container import get_config, get_repository, _create_buscar_faturas

router = APIRouter(prefix="/api/faturas", tags=["faturas"])

# Exemplos para documentação Swagger
_EXAMPLE_PERIODO = "02/2026"
_EXAMPLE_PERIODO_ALT = "01/2026"


class PeriodoSchema(BaseModel):
    ano: int
    mes: int
    periodo: str
    valorTotal: float
    quantidadeDebitos: int
    existeDebitoVencido: bool
    provedor: str | None = None  # aguas | luz (para provedor=todos)


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
                            "periodo": _EXAMPLE_PERIODO,
                            "valorTotal": 62.57,
                            "quantidadeDebitos": 1,
                            "existeDebitoVencido": False,
                        },
                        {
                            "ano": 2026,
                            "mes": 1,
                            "periodo": _EXAMPLE_PERIODO_ALT,
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
                        "periodo": _EXAMPLE_PERIODO,
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
                            "referencia": _EXAMPLE_PERIODO,
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


class FaturaEscolaItemSchema(BaseModel):
    id: int
    nome_aluno: str
    ano: int
    mes: int
    valor: float
    dataValidadePix: str
    statusPix: str
    codigoPix: str
    qrcodeBase64: str
    createdAt: str


class ListaFaturasEscolaResponse(BaseModel):
    itens: list[FaturaEscolaItemSchema]
    total: int


def _formatar_debito_mobile(d: dict) -> dict:
    """Formata débito para consumo no app (valor, data, codigoBarras, codigoPix, dataValidadePix, statusPix, qrcodeBase64)."""
    num = d.get("numeroAviso") or d.get("id")
    valor = d.get("valorFatura") or d.get("valor") or d.get("TotalToPay") or d.get("Value") or 0
    return {
        "id": num if num else None,
        "referencia": d.get("referencia", d.get("ReferenceDate", d.get("periodo", ""))),
        "valor": float(valor),
        "dataVencimento": str(d.get("dataVencimento", d.get("DueDate", d.get("vencimento", "")))),
        "codigoBarras": d.get("codigoBarrasDigitavel", d.get("Number", d.get("codigoBarras", ""))),
        "codigoPix": d.get("codigoPIX", d.get("codigoPix", "")),
        "dataValidadePix": d.get("dataValidadePix", ""),
        "statusPix": d.get("statusPix", "ativo"),
        "qrcodeBase64": d.get("qrcodeBase64", ""),
        "aluno": d.get("BeneficiaryName", d.get("aluno", "")),
        "status": d.get("statusFatura", d.get("status", "")),
        "situacaoPagamento": d.get("situacaoPagamento", ""),
    }


def _fetch_fatura_from_api(ano: int, mes: int) -> tuple[dict, list]:
    """Busca fatura via API (login + scrape). Retorna (content, debitos_raw)."""
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
    except ValueError as e:
        raise HTTPException(500, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    content = raw.get("content", {})
    debitos_raw = content.get("debitos", [])
    content.setdefault("valorTotalDebitos", sum(d.get("valorFatura", 0) for d in debitos_raw))
    content.setdefault("quantidadeDebitos", len(debitos_raw))
    content.setdefault("existeDebitoVencido", any(d.get("statusFatura") == "Atrasada" for d in debitos_raw))
    content.setdefault("consultadoEm", datetime.now().isoformat())
    return content, debitos_raw


def _fetch_fatura_from_db(repository, ano: int, mes: int) -> tuple[dict, list]:
    """Busca fatura do banco (água). Retorna (content, debitos_raw)."""
    result = repository.buscar_ultima_consulta(ano, mes)
    if not result:
        raise HTTPException(404, "Nenhuma fatura encontrada para este período")
    return result, result.get("debitos", [])


def _fetch_fatura_luz_from_db(ano: int, mes: int) -> tuple[dict, list]:
    """Busca fatura de luz do banco. Retorna (content, debitos_raw) normalizado."""
    from atlasfetch.infrastructure.persistence.database import buscar_fatura_luz

    result = buscar_fatura_luz(ano, mes)
    if not result:
        raise HTTPException(404, "Nenhuma fatura de luz encontrada para este período")
    # Normalizar para formato compatível (debitos pode vir de estrutura diferente)
    debitos_raw = result.get("debitos", result.get("consumos", []))
    if isinstance(debitos_raw, dict):
        debitos_raw = [debitos_raw]
    content = {
        "valorTotalDebitos": result.get("valorTotal", result.get("valor", 0)),
        "quantidadeDebitos": len(debitos_raw) or 1,
        "existeDebitoVencido": False,
        "consultadoEm": result.get("consultadoEm", ""),
    }
    return content, debitos_raw


def _fetch_fatura_escola_from_db(ano: int, mes: int) -> tuple[dict, list]:
    """Busca parcelas escolares do banco."""
    from atlasfetch.infrastructure.persistence.database import buscar_fatura_escola

    result = buscar_fatura_escola(ano, mes)
    if not result:
        raise HTTPException(404, "Nenhuma parcela escolar encontrada para este período")
    debitos_raw = result.get("debitos", [])
    content = {
        "valorTotalDebitos": result.get("valorTotalDebitos", 0),
        "quantidadeDebitos": result.get("quantidadeDebitos", 0),
        "existeDebitoVencido": result.get("existeDebitoVencido", False),
        "consultadoEm": result.get("consultadoEm", ""),
    }
    return content, debitos_raw


@router.get(
    "/escola",
    response_model=ListaFaturasEscolaResponse,
)
async def listar_faturas_escola_api(
    ano: int | None = Query(None, description="Filtra por ano (opcional)"),
    mes: int | None = Query(None, ge=1, le=12, description="Filtra por mês (opcional)"),
    limit: int = Query(100, ge=1, le=500, description="Quantidade máxima de registros"),
):
    """Lista registros de faturas escolares com dados PIX persistidos no banco."""
    from atlasfetch.infrastructure.persistence.database import listar_faturas_escola

    itens = listar_faturas_escola(ano=ano, mes=mes, limit=limit)
    return {"itens": itens, "total": len(itens)}


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
                                "periodo": _EXAMPLE_PERIODO,
                                "valorTotal": 62.57,
                                "quantidadeDebitos": 1,
                                "existeDebitoVencido": False,
                            },
                            {
                                "ano": 2026,
                                "mes": 1,
                                "periodo": _EXAMPLE_PERIODO_ALT,
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
async def listar_periodos(
    provedor: str = Query(
        "aguas",
        description="aguas=água | luz=energia | escola=parcelas escolares | todos/ambos=todos",
    ),
):
    """
    Lista períodos com faturas disponíveis.
    Para IA: "quais faturas tenho?" → provedor=todos
    """
    provedor_norm = (provedor or "aguas").strip().lower()

    if provedor_norm == "luz":
        from atlasfetch.infrastructure.persistence.database import listar_periodos_luz

        periodos = [dict(p, provedor="luz") for p in listar_periodos_luz()]
    elif provedor_norm == "escola":
        from atlasfetch.infrastructure.persistence.database import listar_periodos_escola

        periodos = [dict(p, provedor="escola") for p in listar_periodos_escola()]
    elif provedor_norm in {"todos", "ambos"}:
        repository = get_repository()
        aguas = [dict(p, provedor="aguas") for p in repository.listar_periodos_disponiveis()]
        from atlasfetch.infrastructure.persistence.database import listar_periodos_luz, listar_periodos_escola

        luz = [dict(p, provedor="luz") for p in listar_periodos_luz()]
        escola = [dict(p, provedor="escola") for p in listar_periodos_escola()]
        periodos = aguas + luz + escola
        periodos.sort(key=lambda x: (x["ano"], x["mes"]), reverse=True)
        periodos = periodos[:50]
    elif provedor_norm == "aguas":
        repository = get_repository()
        periodos = [dict(p, provedor="aguas") for p in repository.listar_periodos_disponiveis()]
    else:
        raise HTTPException(400, "provedor inválido. Use: aguas, luz, escola, todos ou ambos")
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
                            "periodo": _EXAMPLE_PERIODO,
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
                                "referencia": _EXAMPLE_PERIODO,
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
    provedor: str = Query(
        "aguas",
        description="aguas=água | luz=energia | escola=parcelas escolares",
    ),
    atualizar: bool = Query(
        False,
        description="Se true, força nova consulta à API (só água; luz usa sync)",
    ),
):
    """
    Retorna fatura de um período (ano/mês).

    - **provedor=aguas**: conta de água
    - **provedor=luz**: conta de luz (Amazonas Energia)
    - **atualizar=false**: lê do banco
    - **atualizar=true** (só água): faz login, busca na API, salva e retorna

    Para IA: "conta de luz do mês 2" → GET /api/faturas/2026/2?provedor=luz
    """
    repository = get_repository()
    if provedor == "luz":
        if atualizar:
            from atlasfetch.infrastructure.external.scrapers import sync_and_save_luz

            sync_and_save_luz()
        content, debitos_raw = _fetch_fatura_luz_from_db(ano, mes)
    elif provedor == "escola":
        if atualizar:
            from atlasfetch.infrastructure.external.scrapers import sync_and_save_escola

            sync_and_save_escola()
        content, debitos_raw = _fetch_fatura_escola_from_db(ano, mes)
    else:
        content, debitos_raw = (
            _fetch_fatura_from_api(ano, mes) if atualizar
            else _fetch_fatura_from_db(repository, ano, mes)
        )
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
