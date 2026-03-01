# Agendamento (Scheduler)

O scheduler executa o scraper em horários definidos e salva as faturas no banco automaticamente.

## Como ativar

### 1. Configure o `.env`

```env
# Ativar o scheduler
SCHEDULER_ENABLED=1

# Data e horário (formato cron)
# minuto hora dia_do_mes mes dia_da_semana
SCHEDULER_CRON=0 6 * * *
```

**Exemplos de SCHEDULER_CRON:**

| Expressão | Descrição |
|-----------|-----------|
| `0 6 * * *` | Todo dia às 6h da manhã |
| `0 0 * * *` | Todo dia à meia-noite |
| `30 8 * * *` | Todo dia às 8h30 |
| `0 6 * * 1` | Toda segunda às 6h |
| `0 6 1 * *` | Todo dia 1º de cada mês às 6h |
| `0 6 15 2 *` | Todo dia 15 de fevereiro às 6h |
| `*/5 * * * *` | A cada 5 minutos (teste) |

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

## O que o job faz

1. Faz login no site Águas de Manaus (Playwright + 2FA)
2. Busca débitos na API Aegea
3. Agrupa por referência (MM/YYYY)
4. Salva no banco (tabelas `consultas` e `debitos`)

## Pré-requisitos

- `.env` com `AGUAS_CPF`, `AGUAS_SENHA`, `AGUAS_MATRICULA`, `AGUAS_SEQUENCIAL`
- **Gmail para 2FA:** configure no `.env` (sem setup script):
  - `GMAIL_USER` = seu e-mail
  - `GMAIL_APP_PASSWORD` = senha de app (https://myaccount.google.com/apppasswords)

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
