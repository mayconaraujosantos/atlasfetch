"""Rotas de sincronização."""

from fastapi import APIRouter, HTTPException

from atlasfetch.api.container import get_config, _create_sincronizar_debitos

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/run")
async def run_sync_now():
    """Executa o job de sincronização imediatamente."""
    config = get_config()
    if not config["cpf"] or not config["senha"]:
        raise HTTPException(500, "AGUAS_CPF e AGUAS_SENHA não configurados")
    if not config["matricula"] or not config["sequencial"]:
        raise HTTPException(500, "AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")

    try:
        use_case = _create_sincronizar_debitos()
        return use_case.execute(
            cpf=config["cpf"],
            senha=config["senha"],
            matricula=config["matricula"],
            sequencial=config["sequencial"],
            zona=config["zona"],
        )
    except Exception as e:
        raise HTTPException(500, str(e))
