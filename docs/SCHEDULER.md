# Agendamento (Scheduler)

O scheduler executa os scrapers em horários definidos. Cada provedor tem seu próprio cron.

## Como ativar

### 1. Configure o `.env`

```env
# Ativar o scheduler
SCHEDULER_ENABLED=1

# Água (Águas de Manaus) - formato: minuto hora dia mes dia_semana
SCHEDULER_CRON=0 6 * * *

# Luz (Amazonas Energia) - cron separado
SCHEDULER_AMAZONAS_ENERGIA_ENABLED=1
SCHEDULER_AMAZONAS_ENERGIA_CRON=0 7 * * *
```

**Formato:** `minuto hora dia_do_mes mes dia_da_semana`

**Exemplos de SCHEDULER_CRON:**

| Expressão | Descrição |
|-----------|-----------|
| `0 6 * * *` | Todo dia às 6h da manhã |
| `0 0 * * *` | Todo dia à meia-noite |
| `30 8 * * *` | Todo dia às 8h30 |
| `0 6 * * 1` | Toda segunda às 6h |
| `0 6 1 * *` | Todo dia 1º de cada mês às 6h |
| `0 6 15 2 *` | Dia 15 de fevereiro às 6h |
| `0 8 10 3 *` | Dia 10 de março às 8h |
| `30 7 25 12 *` | Dia 25 de dezembro às 7h30 |
| `*/5 * * * *` | A cada 5 minutos (teste) |

**Para agendar em dia X, mês X e hora X:**

```
# minuto  hora  dia  mês  dia_semana
  0       8     10   3    *
```
= Dia **10** do mês **3** (março) às **8h**.

**Alternativa (simples):**

```env
SCHEDULER_ENABLED=1
SCHEDULER_HOUR=6
SCHEDULER_MINUTE=0
```
(Executa todo dia às 6h)

### 2. Inicie o scheduler

Em um terminal separado (ou em background):

```bash
make scheduler
```

Ou:

```bash
python scheduler.py --schedule
```

O processo fica rodando e executa o job nos horários configurados.

## O que os jobs fazem

### Água (Águas de Manaus)
1. Faz login no site (Playwright + 2FA)
2. Busca débitos na API Aegea
3. Salva no banco (tabelas `consultas` e `debitos`)

### Luz (Amazonas Energia)
1. Usa token salvo no banco (sem navegador)
2. Busca consumos na API Pigz
3. Rode `make setup-amazonas-energia` uma vez para obter o token

## Pré-requisitos

### Água
- `.env` com `AGUAS_CPF`, `AGUAS_SENHA`, `AGUAS_MATRICULA`, `AGUAS_SEQUENCIAL`
- **Gmail para 2FA:** `GMAIL_USER` e `GMAIL_APP_PASSWORD` no `.env`

### Luz
- `make setup-amazonas-energia` – abre navegador, você resolve reCAPTCHA, token é salvo
- Jobs agendados usam o token (sem abrir navegador)

## Executar uma vez (sem agendar)

```bash
make run
# ou
make sync
```

## Rodar em produção

Use `systemd`, `supervisor` ou `cron` para manter o scheduler rodando:

**Exemplo systemd** (`/etc/systemd/system/atlasfetch-scheduler.service`):

```ini
[Unit]
Description=Atlasfetch Scheduler
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/caminho/para/atlasfetch
ExecStart=/caminho/para/atlasfetch/.venv/bin/python scheduler.py --schedule
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable atlasfetch-scheduler
sudo systemctl start atlasfetch-scheduler
```
