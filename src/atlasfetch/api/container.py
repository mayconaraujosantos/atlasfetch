"""Container de dependências - monta os casos de uso com seus adaptadores."""

import os

from dotenv import load_dotenv

from atlasfetch.application.use_cases.buscar_faturas import BuscarFaturasUseCase
from atlasfetch.application.use_cases.sincronizar_debitos import SincronizarDebitosUseCase
from atlasfetch.infrastructure.external.aegea_client import AegeaDebitoClient
from atlasfetch.infrastructure.external.b2c_auth_adapter import B2CAuthAdapter
from atlasfetch.infrastructure.persistence.sqlalchemy_repository import (
    SqlAlchemyConsultaRepository,
)

load_dotenv()


def _create_repository():
    from atlasfetch.infrastructure.persistence.database import get_session
    return SqlAlchemyConsultaRepository(get_session=get_session)


def get_repository():
    return _create_repository()


def _create_buscar_faturas():
    return BuscarFaturasUseCase(
        auth=B2CAuthAdapter(),
        debito_api=AegeaDebitoClient(),
        repository=_create_repository(),
    )


def _create_sincronizar_debitos():
    return SincronizarDebitosUseCase(
        auth=B2CAuthAdapter(),
        debito_api=AegeaDebitoClient(),
        repository=_create_repository(),
    )


def get_config():
    """Retorna configuração do .env."""
    return {
        "cpf": os.environ.get("AGUAS_CPF", ""),
        "senha": os.environ.get("AGUAS_SENHA", ""),
        "matricula": os.environ.get("AGUAS_MATRICULA", ""),
        "sequencial": os.environ.get("AGUAS_SEQUENCIAL", ""),
        "zona": os.environ.get("AGUAS_ZONA", "1"),
    }
