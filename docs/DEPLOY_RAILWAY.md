# Deploy no Railway

Guia para rodar a API e o job de sync no Railway.

## Arquitetura no Railway

1. **API** – serviço web (uvicorn)
2. **PostgreSQL** – banco do Railway
3. **Job/Scheduler** – execução agendada do sync

## 1. Criar projeto no Railway

1. Crie um projeto em [railway.app](https://railway.app)
2. Adicione o **PostgreSQL** (Add Service → Database → PostgreSQL)
3. Adicione um **Service** para a API (deploy do repositório)

## 2. Variáveis de ambiente

No Railway, configure as variáveis do serviço da API:

```
# Railway oferece Postgres; local usa SQLite por padrão
DATABASE_URL=${{Postgres.DATABASE_URL}}
AGUAS_CPF=...
AGUAS_SENHA=...
AGUAS_MATRICULA=...
AGUAS_SEQUENCIAL=...
AGUAS_ZONA=1
```

**2FA (código por e-mail):** use **IMAP** (mais simples no Railway):

```
GMAIL_USER=seu@email.com
GMAIL_APP_PASSWORD=senha_de_app
```

> **Por quê IMAP?** O Gmail OAuth exige `make setup-gmail` com navegador. No Railway não há browser. Com IMAP, basta configurar as variáveis acima.

## 3. Gmail OAuth (alternativa ao IMAP)

Se quiser usar OAuth em vez de IMAP:

1. **Localmente**, apontando para o banco do Railway:
   ```bash
   # No .env local, use o DATABASE_URL do Railway
   DATABASE_URL=postgresql://postgres:xxx@xxx.railway.app:5432/railway

   make setup-gmail
   ```
2. O script abre o navegador, você autoriza e os dados vão para o PostgreSQL do Railway.
3. No Railway, a API lê `credentials_json` e `token_json` da tabela `gmail_oauth_config`.

## 4. Rodar o job de sync

### Opção A: Railway Cron Jobs

Se o Railway oferecer Cron Jobs:

- **Comando:** `python scheduler.py`
- **Schedule:** ex. `0 6 * * *` (todo dia às 6h)

O `scheduler.py` sem `--schedule` executa o sync uma vez e encerra.

### Opção B: Worker separado

Crie um segundo serviço (Worker) que rode o scheduler em modo daemon:

- **Start Command:** `python scheduler.py --schedule`
- **Variáveis:** mesmas da API (`DATABASE_URL`, `AGUAS_*`, `GMAIL_*`, `SCHEDULER_ENABLED=1`, `SCHEDULER_CRON=0 6 * * *`)

### Opção C: Cron externo

Use um serviço externo (ex: [cron-job.org](https://cron-job.org)) para chamar um endpoint da API:

1. Adicione um endpoint protegido, ex: `POST /api/sync/run` (já existe)
2. Proteja com um token ou API key
3. Configure o cron externo para fazer `POST https://sua-api.railway.app/api/sync/run` no horário desejado

## 5. Comandos de deploy

**Procfile** (se usar):

```
web: uvicorn api:app --host 0.0.0.0 --port $PORT
```

**railway.json** (opcional):

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn api:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## Resumo: OAuth2 no Railway

| Método | Como funciona |
|--------|----------------|
| **IMAP** | `GMAIL_USER` + `GMAIL_APP_PASSWORD` no .env. Sem setup. |
| **OAuth** | Rode `make setup-gmail` local com `DATABASE_URL` do Railway. Depois a API lê do banco. |

O token OAuth fica na tabela `gmail_oauth_config`. Quando expira, o Google renova o refresh. Se falhar, rode `make setup-gmail` de novo localmente.
