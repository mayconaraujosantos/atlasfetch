-- -------------------------------------------------------------
-- -------------------------------------------------------------
-- TablePlus 1.4.2
--
-- https://tableplus.com/
--
-- Database: postgres
-- Generation Time: 2026-02-28 22:28:08.116891
-- -------------------------------------------------------------

-- This script only contains the table creation statements and does not fully represent the table in database. It's still missing: indices, triggers. Do not use it as backup.

-- Sequences
CREATE SEQUENCE IF NOT EXISTS consultas_id_seq;

-- Table Definition
CREATE TABLE "public"."consultas" (
    "id" int4 NOT NULL DEFAULT nextval('consultas_id_seq'::regclass),
    "matricula" varchar NOT NULL,
    "sequencial_responsavel" varchar NOT NULL,
    "zona_ligacao" int4 NOT NULL,
    "quantidade_debitos" int4 NOT NULL,
    "valor_total_debitos" float8 NOT NULL,
    "existe_debito_vencido" bool NOT NULL,
    "ano_filtro" int4 NOT NULL,
    "mes_filtro" int4 NOT NULL,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

-- This script only contains the table creation statements and does not fully represent the table in database. It's still missing: indices, triggers. Do not use it as backup.

-- Sequences
CREATE SEQUENCE IF NOT EXISTS debitos_id_seq;

-- Table Definition
CREATE TABLE "public"."debitos" (
    "id" int4 NOT NULL DEFAULT nextval('debitos_id_seq'::regclass),
    "consulta_id" int4 NOT NULL,
    "referencia" varchar NOT NULL,
    "data_vencimento" timestamp NOT NULL,
    "valor_fatura" float8 NOT NULL,
    "situacao_pagamento" varchar NOT NULL,
    "codigo_tributo" varchar NOT NULL,
    "ano_lancamento" int4 NOT NULL,
    "numero_aviso" int4 NOT NULL,
    "numero_emissao" int4 NOT NULL,
    "zona_ligacao" int4 NOT NULL,
    "status_fatura" varchar NOT NULL,
    "consumo" int4 NOT NULL,
    "codigo_barras_digitavel" varchar NOT NULL,
    "codigo_pix" text NOT NULL,
    "contrato_encerrado" bool NOT NULL,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

-- This script only contains the table creation statements and does not fully represent the table in database. It's still missing: indices, triggers. Do not use it as backup.

-- Sequences
CREATE SEQUENCE IF NOT EXISTS gmail_oauth_config_id_seq;

-- Table Definition
CREATE TABLE "public"."gmail_oauth_config" (
    "id" int4 NOT NULL DEFAULT nextval('gmail_oauth_config_id_seq'::regclass),
    "credentials_json" text,
    "token_json" text,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

-- Dados iniciais: use make run ou make sync para popular via API.
-- Gmail OAuth: use make setup-gmail para configurar credentials/token no banco.
-- Amazonas Energia: use make setup-amazonas-energia para configurar token (luz).

-- Sequences
CREATE SEQUENCE IF NOT EXISTS amazonas_energia_token_id_seq;

-- Table Definition
CREATE TABLE IF NOT EXISTS "public"."amazonas_energia_token" (
    "id" int4 NOT NULL DEFAULT nextval('amazonas_energia_token_id_seq'::regclass),
    "auth_header" text NOT NULL,
    "unit_id" varchar(20) NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

-- Sequences
CREATE SEQUENCE IF NOT EXISTS faturas_luz_id_seq;

-- Table Definition
CREATE TABLE IF NOT EXISTS "public"."faturas_luz" (
    "id" int4 NOT NULL DEFAULT nextval('faturas_luz_id_seq'::regclass),
    "unit_id" varchar(20) NOT NULL,
    "ano" int4 NOT NULL,
    "mes" int4 NOT NULL,
    "data_json" text NOT NULL,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT uq_faturas_luz_unit_ano_mes UNIQUE (unit_id, ano, mes)
);

-- Para tabelas já existentes sem a constraint:
-- ALTER TABLE faturas_luz ADD CONSTRAINT uq_faturas_luz_unit_ano_mes UNIQUE (unit_id, ano, mes);

