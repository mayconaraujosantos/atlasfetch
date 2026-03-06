-- Adiciona constraint UNIQUE em faturas_luz (unit_id, ano, mes) - PostgreSQL
-- Para SQLite, use: python scripts/migrate_faturas_luz_unique.py
-- Execute: psql $DATABASE_URL -f scripts/add_unique_faturas_luz.sql

DO $$
BEGIN
  -- Remove duplicatas (mantém a mais recente por created_at)
  DELETE FROM faturas_luz a
  USING faturas_luz b
  WHERE a.id < b.id
    AND a.unit_id = b.unit_id
    AND a.ano = b.ano
    AND a.mes = b.mes;

  -- Adiciona constraint se não existir
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_faturas_luz_unit_ano_mes'
  ) THEN
    ALTER TABLE faturas_luz
    ADD CONSTRAINT uq_faturas_luz_unit_ano_mes UNIQUE (unit_id, ano, mes);
  END IF;
END $$;
