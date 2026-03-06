#!/usr/bin/env python3
"""
Migração: remove coluna redundante student_id de faturas_escola.
Mantém apenas nome_aluno como identificador de aluno por período.
Executa: python scripts/migrate_faturas_escola_remove_student_id.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///atlasfetch.db")
IS_SQLITE = "sqlite" in DATABASE_URL


def run_migration():
    from sqlalchemy import create_engine, text

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if IS_SQLITE else {},
    )

    with engine.connect() as conn:
        if IS_SQLITE:
            conn.execute(text("""
                CREATE TABLE faturas_escola_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_aluno VARCHAR(200) NOT NULL,
                    ano INTEGER NOT NULL,
                    mes INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    valor REAL,
                    data_validade_pix VARCHAR(50),
                    status_pix VARCHAR(20),
                    qrcode_base64 TEXT,
                    codigo_pix TEXT,
                    UNIQUE(nome_aluno, ano, mes)
                )
            """))
            conn.execute(text("""
                INSERT INTO faturas_escola_new
                    (id, nome_aluno, ano, mes, created_at, valor, data_validade_pix, status_pix, qrcode_base64, codigo_pix)
                SELECT
                    id,
                    COALESCE(NULLIF(nome_aluno, ''), NULLIF(student_id, ''), 'aluno_sem_nome'),
                    ano,
                    mes,
                    created_at,
                    valor,
                    data_validade_pix,
                    status_pix,
                    qrcode_base64,
                    codigo_pix
                FROM faturas_escola
            """))
            conn.execute(text("DROP TABLE faturas_escola"))
            conn.execute(text("ALTER TABLE faturas_escola_new RENAME TO faturas_escola"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_faturas_escola_aluno_ano_mes ON faturas_escola(nome_aluno, ano, mes)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_faturas_escola_nome_aluno ON faturas_escola(nome_aluno)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_faturas_escola_ano ON faturas_escola(ano)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_faturas_escola_mes ON faturas_escola(mes)"))
            conn.commit()
            print("SQLite: tabela faturas_escola recriada sem student_id")
        else:
            # PostgreSQL
            conn.execute(text("""
                UPDATE faturas_escola
                SET nome_aluno = COALESCE(NULLIF(nome_aluno, ''), NULLIF(student_id, ''), 'aluno_sem_nome')
                WHERE nome_aluno IS NULL OR nome_aluno = ''
            """))
            conn.execute(text("ALTER TABLE faturas_escola ALTER COLUMN nome_aluno SET NOT NULL"))
            conn.execute(text("ALTER TABLE faturas_escola DROP CONSTRAINT IF EXISTS uq_faturas_escola_student_ano_mes"))
            conn.execute(text("ALTER TABLE faturas_escola ADD CONSTRAINT uq_faturas_escola_aluno_ano_mes UNIQUE (nome_aluno, ano, mes)"))
            conn.execute(text("DROP INDEX IF EXISTS ix_faturas_escola_student_id"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_faturas_escola_nome_aluno ON faturas_escola(nome_aluno)"))
            conn.execute(text("ALTER TABLE faturas_escola DROP COLUMN IF EXISTS student_id"))
            conn.commit()
            print("PostgreSQL: coluna student_id removida")


if __name__ == "__main__":
    print("Migrando faturas_escola para remover student_id...")
    run_migration()
    print("OK.")
