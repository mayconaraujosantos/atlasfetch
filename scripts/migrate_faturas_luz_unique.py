#!/usr/bin/env python3
"""Adiciona constraint UNIQUE(unit_id, ano, mes) em faturas_luz.
Suporta SQLite e PostgreSQL."""

import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from sqlalchemy import text

from atlasfetch.infrastructure.persistence.database import engine


def run_postgres():
    sql = """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_faturas_luz_unit_ano_mes'
      ) THEN
        DELETE FROM faturas_luz a
        USING faturas_luz b
        WHERE a.id < b.id
          AND a.unit_id = b.unit_id
          AND a.ano = b.ano
          AND a.mes = b.mes;
        ALTER TABLE faturas_luz
        ADD CONSTRAINT uq_faturas_luz_unit_ano_mes UNIQUE (unit_id, ano, mes);
        RAISE NOTICE 'Constraint uq_faturas_luz_unit_ano_mes adicionada.';
      ELSE
        RAISE NOTICE 'Constraint já existe.';
      END IF;
    END $$;
    """
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


def run_sqlite():
    with engine.connect() as conn:
        # Verificar se índice já existe
        r = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='uq_faturas_luz_unit_ano_mes'"
            )
        ).fetchone()
        if r:
            print("Constraint já existe.")
            return

        # Criar tabela nova com constraint
        conn.execute(text("""
            CREATE TABLE faturas_luz_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                unit_id VARCHAR(20) NOT NULL,
                ano INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                created_at DATETIME,
                UNIQUE (unit_id, ano, mes)
            )
        """))
        # Copiar dados deduplicados (mantém o de menor id por grupo)
        conn.execute(text("""
            INSERT INTO faturas_luz_new (id, unit_id, ano, mes, data_json, created_at)
            SELECT id, unit_id, ano, mes, data_json, created_at
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY unit_id, ano, mes ORDER BY id) rn
                FROM faturas_luz
            ) WHERE rn = 1
        """))
        conn.execute(text("DROP TABLE faturas_luz"))
        conn.execute(text("ALTER TABLE faturas_luz_new RENAME TO faturas_luz"))
        conn.commit()
        print("Constraint uq_faturas_luz_unit_ano_mes adicionada.")


if __name__ == "__main__":
    dialect = engine.dialect.name
    if dialect == "sqlite":
        run_sqlite()
    elif dialect == "postgresql":
        run_postgres()
    else:
        print(f"Dialeto {dialect} não suportado. Use SQLite ou PostgreSQL.")
        sys.exit(1)
    print("Migração concluída.")
