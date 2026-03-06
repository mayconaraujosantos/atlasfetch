#!/usr/bin/env python3
"""
Login na Agência Amazonas Energia e busca payload do endpoint:
GET /api/faturas/abertas

Uso:
  python scripts/fetch_amazonas_faturas_abertas.py
  AMAZONAS_ENERGIA_CLIENT_ID=18839258 python scripts/fetch_amazonas_faturas_abertas.py
"""

import json
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
from atlasfetch.infrastructure.external.scrapers.amazonas_energia import (
    login_and_fetch_faturas_abertas,
)


if __name__ == "__main__":
    init_db()
    print("Abrindo login da Agência Amazonas Energia...")
    result = login_and_fetch_faturas_abertas(headless=False, wait_manual_seconds=120)
    print(f"OK. unit_id={result['unit_id']} | client_id={result['client_id']}")
    print(json.dumps(result["payload"], ensure_ascii=False, indent=2))
