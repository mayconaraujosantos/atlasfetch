# Scraper Amazonas Energia (luz)

Scraper para faturas de energia elétrica da Amazonas Energia. Funciona com **agendamento** sem abrir navegador.

## Fluxo

1. **Login automático** (recomendado): configure CPF, senha e `OPENAI_API_KEY` – o scheduler faz login em background quando o token não existe ou expira
2. **Login manual**: rode `make setup-amazonas-energia` – abre o navegador, você resolve o reCAPTCHA
3. **Jobs agendados**: usam o token salvo no banco – sem navegador

## Configuração

### 1. Variáveis de ambiente (.env)

```env
AMAZONAS_ENERGIA_CPF=015.966.702-07
AMAZONAS_ENERGIA_SENHA=sua_senha
AMAZONAS_ENERGIA_UNIT_ID=991643  # opcional, capturado no login
```

### 2. Login automático (headless, sem interação)

Com `OPENAI_API_KEY` configurado, o scraper resolve o reCAPTCHA via IA e faz login em modo headless (navegador em segundo plano). O scheduler tenta isso automaticamente quando o token não existe:

```env
OPENAI_API_KEY=sk-xxx
AMAZONAS_ENERGIA_CPF=12345678900
AMAZONAS_ENERGIA_SENHA=sua_senha
```

Instale o pacote opcional: `pip install openai`

### 3. Setup manual do token

Quando não usar login automático, rode quando não houver token ou quando expirar (401):

```bash
make setup-amazonas-energia
```

Abre o navegador, preenche o form. Você resolve o reCAPTCHA. O scraper clica em Entrar a cada 8s e salva o token.

### 4. Agendamento

```env
# Ativar job de luz
SCHEDULER_AMAZONAS_ENERGIA_ENABLED=1

# Cron separado (ex: todo dia às 7h)
SCHEDULER_AMAZONAS_ENERGIA_CRON=0 7 * * *
```

Formato: `minuto hora dia_do_mes mes dia_da_semana`

## Uso programático

```python
from atlasfetch.infrastructure.external.scrapers import (
    fetch_consumes_scheduled,
    amazonas_energia_login,
)

# Job agendado - usa token salvo, sem navegador
consumos = fetch_consumes_scheduled()

# Login manual (para setup) - abre navegador
result = amazonas_energia_login()
```

## Múltiplas unidades

Para várias unidades consumidoras (ex: casa + comércio):

```env
AMAZONAS_ENERGIA_UNIT_IDS=991643,24988197
```

Ou uma única: `AMAZONAS_ENERGIA_UNIT_ID=991643`

O job agendado busca e salva faturas de todas as unidades.
