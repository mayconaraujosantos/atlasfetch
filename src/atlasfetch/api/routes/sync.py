"""Rotas de sincronização."""

import os

from fastapi import APIRouter, HTTPException, Query

from atlasfetch.api.container import get_config, _create_sincronizar_debitos

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/run")
async def run_sync_now(
    provedor: str = Query(
        "todos",
        description="aguas=água | luz=energia | escola=parcelas escolares | todos=ambos",
    ),
):
    """
    Executa sincronização imediatamente.
    Para IA: "sincronizar minhas contas" → POST /api/sync/run?provedor=todos
    """
    results = {}
    if provedor in ("aguas", "todos"):
        config = get_config()
        if not config["cpf"] or not config["senha"]:
            raise HTTPException(500, "AGUAS_CPF e AGUAS_SENHA não configurados")
        if not config["matricula"] or not config["sequencial"]:
            raise HTTPException(500, "AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")
        try:
            use_case = _create_sincronizar_debitos()
            results["aguas"] = use_case.execute(
                cpf=config["cpf"],
                senha=config["senha"],
                matricula=config["matricula"],
                sequencial=config["sequencial"],
                zona=config["zona"],
            )
        except Exception as e:
            raise HTTPException(500, str(e))

    if provedor in ("luz", "todos"):
        try:
            from atlasfetch.infrastructure.external.scrapers import sync_and_save_luz

            results["luz"] = sync_and_save_luz()
        except Exception as e:
            if provedor == "luz":
                raise HTTPException(500, str(e))
            results["luz"] = {"erro": str(e)}

    if provedor in ("escola", "todos"):
        if not os.environ.get("EDUCADVENTISTA_CPF") or not os.environ.get("EDUCADVENTISTA_DATA_NASCIMENTO"):
            if provedor == "escola":
                raise HTTPException(500, "EDUCADVENTISTA_CPF e EDUCADVENTISTA_DATA_NASCIMENTO não configurados")
            results["escola"] = {"erro": "EDUCADVENTISTA_CPF e EDUCADVENTISTA_DATA_NASCIMENTO não configurados"}
        else:
            try:
                from atlasfetch.infrastructure.external.scrapers import sync_and_save_escola

                results["escola"] = sync_and_save_escola()
            except Exception as e:
                if provedor == "escola":
                    raise HTTPException(500, str(e))
                results["escola"] = {"erro": str(e)}

    return results
