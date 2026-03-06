#!/usr/bin/env python3
"""
Configura o token da Amazonas Energia para uso em jobs agendados.

Rode este script quando:
- Primeira vez (token não existe)
- Token expirou (job retorna 401)

O script abre o navegador, você resolve o reCAPTCHA e clica em Entrar.
O token é salvo no banco e usado pelos jobs agendados (sem navegador).
"""

import logging
import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

from atlasfetch.infrastructure.persistence.database import init_db
from atlasfetch.infrastructure.external.scrapers.amazonas_energia import login

if __name__ == "__main__":
    init_db()
    print("Abrindo navegador para login na Agência Amazonas Energia...")
    result = login(headless=False)
    print(f"Token salvo. unit_id={result['unit_id'] or '(não capturado)'}")
    if result.get("client_id"):
        print(f"x-client-id capturado: {result['client_id']}")
        print("Opcional: salve no .env como AMAZONAS_ENERGIA_CLIENT_ID=<valor>")
    if not result.get("unit_id"):
        print("Se unit_id não foi capturado, adicione no .env: AMAZONAS_ENERGIA_UNIT_ID=991643")
    print("Jobs agendados usarão este token (sem abrir navegador).")
