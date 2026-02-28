"""Rotas de faturas."""

from fastapi import APIRouter, HTTPException, Query

from atlasfetch.api.container import get_config, get_repository, _create_buscar_faturas

router = APIRouter(prefix="/api/faturas", tags=["faturas"])


@router.get("/{ano}/{mes}")
@router.get("/{ano}/{mes}/{dia}")
async def get_faturas(
    ano: int,
    mes: int,
    dia: int | None = None,
    client_id: str | None = Query(None, description="ID do cliente (futuro multi-tenant)"),
):
    """Consulta faturas por data. Faz login, busca na API Aegea, salva no banco."""
    if not ano or not mes:
        raise HTTPException(400, "ano e mes são obrigatórios")
    if mes < 1 or mes > 12:
        raise HTTPException(400, "mes deve estar entre 1 e 12")

    config = get_config()
    if not config["cpf"] or not config["senha"]:
        raise HTTPException(500, "AGUAS_CPF e AGUAS_SENHA não configurados")
    if not config["matricula"] or not config["sequencial"]:
        raise HTTPException(500, "AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")

    try:
        use_case = _create_buscar_faturas()
        return use_case.execute(
            ano=ano,
            mes=mes,
            cpf=config["cpf"],
            senha=config["senha"],
            matricula=config["matricula"],
            sequencial=config["sequencial"],
            zona=config["zona"],
        )
    except ValueError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ano}/{mes}/historico")
async def get_faturas_historico(ano: int, mes: int):
    """Retorna faturas já salvas no banco (sem nova consulta)."""
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
