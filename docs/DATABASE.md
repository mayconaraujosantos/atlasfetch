# Diagrama do Banco de Dados

## Modelo de Dados (SQLite / PostgreSQL)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           consultas                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  id                    SERIAL PRIMARY KEY                                │
│  matricula             VARCHAR(20)  [index]                             │
│  sequencial_responsavel VARCHAR(20)                                      │
│  zona_ligacao          INTEGER  DEFAULT 1                                │
│  quantidade_debitos    INTEGER                                           │
│  valor_total_debitos   FLOAT                                             │
│  existe_debito_vencido BOOLEAN                                           │
│  ano_filtro            INTEGER  [index]   ← ano da requisição            │
│  mes_filtro            INTEGER  [index]   ← mês da requisição           │
│  created_at            TIMESTAMP  DEFAULT now()                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1
                                    │
                                    │ N
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            debitos                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  id                      SERIAL PRIMARY KEY                              │
│  consulta_id             INTEGER  NOT NULL  [FK → consultas.id] [index]  │
│  referencia              VARCHAR(20)  [index]   ← "01/2026"               │
│  data_vencimento         TIMESTAMP                                         │
│  valor_fatura            FLOAT                                             │
│  situacao_pagamento      VARCHAR(10)                                      │
│  codigo_tributo          VARCHAR(50)                                       │
│  ano_lancamento          INTEGER                                           │
│  numero_aviso            INTEGER  [index]   ← único por fatura            │
│  numero_emissao          INTEGER                                           │
│  zona_ligacao            INTEGER                                           │
│  status_fatura           VARCHAR(50)   ← ex: "Atrasada"                   │
│  consumo                 INTEGER                                           │
│  codigo_barras_digitavel VARCHAR(100)                                      │
│  codigo_pix              TEXT                                              │
│  contrato_encerrado      BOOLEAN  DEFAULT false                           │
│  created_at              TIMESTAMP  DEFAULT now()                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Diagrama ER (Mermaid)

```mermaid
erDiagram
    consultas ||--o{ debitos : "tem"
    consultas {
        int id PK
        varchar matricula
        varchar sequencial_responsavel
        int zona_ligacao
        int quantidade_debitos
        float valor_total_debitos
        boolean existe_debito_vencido
        int ano_filtro
        int mes_filtro
        timestamp created_at
    }
    debitos {
        int id PK
        int consulta_id FK
        varchar referencia
        timestamp data_vencimento
        float valor_fatura
        varchar situacao_pagamento
        varchar codigo_tributo
        int ano_lancamento
        int numero_aviso
        int numero_emissao
        int zona_ligacao
        varchar status_fatura
        int consumo
        varchar codigo_barras_digitavel
        text codigo_pix
        boolean contrato_encerrado
        timestamp created_at
    }
```

## Tabela gmail_oauth_config

Armazena credentials e token do Gmail OAuth (2FA) em vez de arquivos.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      gmail_oauth_config                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  id                SERIAL PRIMARY KEY                                    │
│  credentials_json TEXT          ← conteúdo de credentials.json         │
│  token_json       TEXT          ← conteúdo de token.json                │
│  updated_at       TIMESTAMP     DEFAULT now()                            │
└─────────────────────────────────────────────────────────────────────────┘
```

O scraper lê do banco primeiro; se vazio, usa os arquivos como fallback.

## Relacionamento

- **Consulta** (1) → (N) **Débitos**: Uma consulta agrupa vários débitos por referência (ano/mês).
- **numero_aviso** em `debitos` é usado para evitar duplicatas ao sincronizar.

## Setup SQLite (padrão)

1. Nenhuma configuração extra. O arquivo `atlasfetch.db` é criado automaticamente no diretório do projeto.

2. Opcional no `.env`:
   ```
   DATABASE_URL=sqlite:///atlasfetch.db
   ```

3. As tabelas são criadas automaticamente na primeira execução (API ou scheduler).

4. Gmail OAuth (opcional): `make setup-gmail` salva credentials e token no banco.
   Se já tiver arquivos: `make migrate-gmail` copia para o banco.

## Setup PostgreSQL (opcional, para deploy)

1. Instale `psycopg2-binary` e configure no `.env`:
   ```
   pip install psycopg2-binary
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/atlasfetch
   ```

2. Crie o banco:
   ```bash
   createdb atlasfetch
   # ou: make db  (Docker)
   ```

3. As tabelas são criadas automaticamente na primeira execução.
