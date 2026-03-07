# Atlasfetch - Makefile
# Uso: make [target]

PYTHON ?= python
VENV ?= .venv
BIN = $(VENV)/bin
PY = $(BIN)/python
PIP = $(BIN)/pip
UVICORN = $(BIN)/uvicorn

.PHONY: help install install-dev venv setup api run sync scheduler setup-gmail setup-amazonas-energia fetch-amazonas-faturas-abertas migrate-gmail db-migrate-faturas-luz db-migrate-faturas-luz-abertas db-migrate-faturas-escola-pix db-migrate-faturas-escola-remove-student-id playwright-install test test-cov test-api clean db db-init

help:
	@echo "Atlasfetch - Comandos disponíveis:"
	@echo ""
	@echo "  make setup                 Cria venv e instala dependências (primeira vez)"
	@echo "  make db                    Inicia PostgreSQL (Docker) - opcional para deploy"
	@echo "  make db-init               Cria tabelas no banco (execute após make db)"
	@echo "  make db-migrate-faturas-luz  Adiciona UNIQUE em faturas_luz (unit_id,ano,mes)"
	@echo "  make db-migrate-faturas-luz-abertas  Cria tabela normalizada de faturas abertas (luz)"
	@echo "  make db-migrate-faturas-escola-pix  Adiciona colunas PIX em faturas_escola"
	@echo "  make db-migrate-faturas-escola-remove-student-id  Remove coluna redundante student_id"
	@echo "  make venv                  Cria ambiente virtual .venv"
	@echo "  make install               Instala dependências (requer venv)"
	@echo "  make api                   Inicia a API (uvicorn na porta 8000)"
	@echo "  make run                   Executa CLI (sync de faturas)"
	@echo "  make sync                  Executa job de sync uma vez"
	@echo "  make sync-escola           Sincroniza parcelas Educação Adventista"
	@echo "  make scheduler             Inicia scheduler (água + luz, cada um com seu cron)"
	@echo "  make setup-gmail           Gmail OAuth - salva no banco (opcional)"
	@echo "  make setup-amazonas-energia  Token Amazonas Energia - login manual, salva no banco"
	@echo "  make fetch-amazonas-faturas-abertas  Login + GET /api/faturas/abertas"
	@echo "  make migrate-gmail         Migra credentials/token dos arquivos para o banco"
	@echo "  make playwright-install   Instala navegadores do Playwright"
	@echo "  make test                  Executa suíte automatizada com pytest"
	@echo "  make test-cov              Executa suíte com relatório de cobertura"
	@echo "  make test-api              Testa API via curl (requer API rodando)"
	@echo "  make clean                 Remove __pycache__, .pyc, etc."
	@echo ""

venv:
	$(PYTHON) -m venv $(VENV)
	@echo "Ambiente criado. Ative com: source $(VENV)/bin/activate"

install:
	@test -d $(VENV) || (echo "Execute 'make venv' primeiro." && exit 1)
	$(PIP) install -r requirements.txt
	@echo "Dependências instaladas."

install-dev:
	@test -d $(VENV) || (echo "Execute 'make venv' primeiro." && exit 1)
	$(PIP) install -r requirements-dev.txt
	@echo "Dependências de desenvolvimento instaladas."

setup: venv install
	@echo "Setup concluído. Ative o venv: source $(VENV)/bin/activate"

api:
	$(UVICORN) api:app --host 0.0.0.0 --port 8000 --reload

run:
	$(PY) main.py

sync:
	$(PY) scheduler.py

sync-escola:
	$(PY) -c "import sys; sys.path.insert(0,'src'); from atlasfetch.infrastructure.persistence.database import init_db; from atlasfetch.infrastructure.external.scrapers import sync_and_save_escola; init_db(); r=sync_and_save_escola(); print('Resultado:', r)"

scheduler:
	$(PY) scheduler.py --schedule

setup-gmail:
	$(PY) scripts/setup_gmail_oauth.py

setup-amazonas-energia:
	$(PY) scripts/setup_amazonas_energia_token.py

fetch-amazonas-faturas-abertas:
	$(PY) scripts/fetch_amazonas_faturas_abertas.py

migrate-gmail:
	$(PY) scripts/migrate_gmail_to_db.py

db:
	docker compose up -d postgres
	@echo "PostgreSQL rodando (opcional). DATABASE_URL=postgresql://postgres:postgres@localhost:5432/atlasfetch"

db-init:
	$(PY) -c "import sys; sys.path.insert(0,'src'); from atlasfetch.infrastructure.persistence.database import init_db; init_db(); print('Tabelas criadas.')"

db-migrate-faturas-luz:
	$(PY) scripts/migrate_faturas_luz_unique.py

db-migrate-faturas-luz-abertas:
	$(PY) scripts/migrate_faturas_luz_abertas.py

db-migrate-faturas-escola-pix:
	$(PY) scripts/migrate_faturas_escola_pix.py

db-migrate-faturas-escola-remove-data-json:
	$(PY) scripts/migrate_faturas_escola_remove_data_json.py

db-migrate-faturas-escola-remove-student-id:
	$(PY) scripts/migrate_faturas_escola_remove_student_id.py

playwright-install:
	$(BIN)/playwright install chromium

test:
	@test -d $(VENV) || (echo "Execute 'make venv' primeiro." && exit 1)
	$(PY) -m pytest

test-cov:
	@test -d $(VENV) || (echo "Execute 'make venv' primeiro." && exit 1)
	$(PY) -m pytest --cov=src/atlasfetch --cov-report=term-missing

test-api:
	@bash scripts/test_api.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Limpeza concluída."
