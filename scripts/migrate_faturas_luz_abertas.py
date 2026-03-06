#!/usr/bin/env python3
"""
Cria tabela faturas_luz_abertas (payload novo da API da agência).
Executa: python scripts/migrate_faturas_luz_abertas.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_migration() -> None:
    from atlasfetch.infrastructure.persistence.database import Base, engine, FaturaLuzAberta

    Base.metadata.create_all(bind=engine, tables=[FaturaLuzAberta.__table__])
    print("Tabela faturas_luz_abertas criada/verificada.")


if __name__ == "__main__":
    run_migration()
