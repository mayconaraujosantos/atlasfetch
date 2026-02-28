# Arquitetura - Clean Architecture

## Estrutura de Pastas

```
atlasfetch/
├── src/
│   └── atlasfetch/
│       ├── domain/              # Camada de domínio
│       │   ├── entities/        # Entidades
│       │   ├── value_objects/   # Objetos de valor
│       │   └── ports/           # Interfaces (contratos)
│       │
│       ├── application/         # Camada de aplicação
│       │   └── use_cases/       # Casos de uso
│       │
│       ├── infrastructure/      # Camada de infraestrutura
│       │   ├── external/       # Adaptadores externos (API, auth)
│       │   └── persistence/    # Adaptadores de persistência
│       │
│       ├── api/                 # Interface HTTP
│       │   ├── routes/
│       │   ├── container.py     # Injeção de dependências
│       │   └── app.py
│       │
│       └── cli/                 # Interface CLI
│
├── api.py           # Entry point: uvicorn api:app
├── main.py          # Entry point: python main.py
├── scheduler.py     # Job agendado
├── scraper.py       # Infra: login Playwright + API Aegea
├── database.py     # Infra: modelos SQLAlchemy
├── email_reader.py # Infra: IMAP
├── gmail_oauth.py   # Infra: Gmail API
└── http_headers.py # Infra: headers HTTP
```

## Camadas

### Domain (domínio)
- **Entities**: `AuthResult` – resultado da autenticação
- **Value Objects**: `parse_referencia`, `referencia_match` – regras de referência MM/YYYY
- **Ports**: interfaces abstratas (`AuthPort`, `DebitoApiPort`, `ConsultaRepositoryPort`)

### Application (aplicação)
- **Use Cases**: orquestram o fluxo
  - `BuscarFaturasUseCase`: login → API → salvar → retornar filtrado
  - `SincronizarDebitosUseCase`: login → API → salvar por referencia

### Infrastructure (infraestrutura)
- **B2CAuthAdapter**: implementa `AuthPort` via Playwright
- **AegeaDebitoClient**: implementa `DebitoApiPort` via requests
- **SqlAlchemyConsultaRepository**: implementa `ConsultaRepositoryPort`

### API (interface)
- **Container**: monta use cases com adaptadores (composição)
- **Routes**: endpoints FastAPI que chamam use cases

## Fluxo de Dependência

```
API/Routes → Use Cases → Ports (interfaces)
                ↑
Infrastructure (implementa Ports)
```

A regra: **dependências apontam para dentro**. O domínio não conhece infraestrutura.

## Como Executar

```bash
# API
uvicorn api:app --host 0.0.0.0 --port 8000

# CLI (sync)
python main.py

# Scheduler standalone
python scheduler.py          # uma execução
python scheduler.py --schedule  # modo daemon
```
