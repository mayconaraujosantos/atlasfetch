#!/usr/bin/env python3
"""
Migração: adiciona colunas PIX à tabela faturas_escola.
Executa: python scripts/migrate_faturas_escola_pix.py
"""

import os
import sys

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///atlasfetch.db")
is_sqlite = "sqlite" in DATABASE_URL

VARCHAR_200 = "VARCHAR(200)"
VARCHAR_50 = "VARCHAR(50)"
VARCHAR_20 = "VARCHAR(20)"

# Colunas a adicionar
COLUMNS = [
    ("valor", "REAL"),
    ("nome_aluno", VARCHAR_200),
    ("data_validade_pix", VARCHAR_50),
    ("status_pix", VARCHAR_20),
    ("codigo_pix", "TEXT"),
    ("qrcode_base64", "TEXT"),
]

# PostgreSQL usa tipos diferentes
PG_TYPES = {
    "REAL": "DOUBLE PRECISION",
    VARCHAR_200: VARCHAR_200,
    VARCHAR_50: VARCHAR_50,
    VARCHAR_20: VARCHAR_20,
    "TEXT": "TEXT",
}


def run_migration():
    from sqlalchemy import create_engine, text

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )

    with engine.connect() as conn:
        for col_name, col_type in COLUMNS:
            try:
                if is_sqlite:
                    sql = f'ALTER TABLE faturas_escola ADD COLUMN {col_name} {col_type}'
                else:
                    pg_type = PG_TYPES.get(col_type, col_type)
                    sql = f'ALTER TABLE faturas_escola ADD COLUMN {col_name} {pg_type}'
                conn.execute(text(sql))
                conn.commit()
                print(f"  + {col_name}")
            except Exception as e:
                err = str(e).lower()
                if "duplicate" in err or "already exists" in err or "exist" in err:
                    print(f"  - {col_name} (já existe)")
                else:
                    raise


if __name__ == "__main__":
    print("Migrando faturas_escola: colunas PIX...")
    run_migration()
    print("OK.")
