# Atlasfetch - Makefile
# Uso: make [target]

PYTHON ?= python
VENV ?= .venv
BIN = $(VENV)/bin
PY = $(BIN)/python
PIP = $(BIN)/pip
UVICORN = $(BIN)/uvicorn

.PHONY: help install venv setup api run sync scheduler setup-gmail playwright-install test clean db db-init

help:
	@echo "Atlasfetch - Comandos disponíveis:"
	@echo ""
	@echo "  make setup           Cria venv e instala dependências (primeira vez)"
	@echo "  make db              Inicia PostgreSQL (Docker) - user/pass: postgres/postgres"
	@echo "  make db-init         Cria tabelas no banco (execute após make db)"
	@echo "  make venv            Cria ambiente virtual .venv"
	@echo "  make install         Instala dependências (requer venv)"
	@echo "  make api             Inicia a API (uvicorn na porta 8000)"
	@echo "  make run             Executa CLI (sync de faturas)"
	@echo "  make sync            Executa job de sync uma vez"
	@echo "  make scheduler       Inicia scheduler (config: .env SCHEDULER_ENABLED=1, SCHEDULER_CRON)"
	@echo "  make setup-gmail     Gmail OAuth - salva no banco (opcional)"
	@echo "  make migrate-gmail   Migra credentials/token dos arquivos para o banco"
	@echo "  make playwright-install  Instala navegadores do Playwright"
	@echo "  make test            Testa API via curl (requer API rodando)"
	@echo "  make clean           Remove __pycache__, .pyc, etc."
	@echo ""

venv:
	$(PYTHON) -m venv $(VENV)
	@echo "Ambiente criado. Ative com: source $(VENV)/bin/activate"

install:
	@test -d $(VENV) || (echo "Execute 'make venv' primeiro." && exit 1)
	$(PIP) install -r requirements.txt
	@echo "Dependências instaladas."

setup: venv install
	@echo "Setup concluído. Ative o venv: source $(VENV)/bin/activate"

api:
	$(UVICORN) api:app --host 0.0.0.0 --port 8000 --reload

run:
	$(PY) main.py

sync:
	$(PY) scheduler.py

scheduler:
	$(PY) scheduler.py --schedule

setup-gmail:
	$(PY) scripts/setup_gmail_oauth.py

migrate-gmail:
	$(PY) scripts/migrate_gmail_to_db.py

db:
	docker compose up -d postgres
	@echo "PostgreSQL rodando. Banco atlasfetch criado. DATABASE_URL=postgresql://postgres:postgres@localhost:5432/atlasfetch"

db-init:
	$(PY) -c "import sys; sys.path.insert(0,'src'); from atlasfetch.infrastructure.persistence.database import init_db; init_db(); print('Tabelas criadas.')"

playwright-install:
	$(BIN)/playwright install chromium

test:
	@bash scripts/test_api.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Limpeza concluída."
