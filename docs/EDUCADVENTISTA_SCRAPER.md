# Scraper Educação Adventista (7edu)

Scraper para parcelas escolares do portal Educação Adventista.

## URL

https://7edu-br.educadventista.org/studentportal/externalpayment

## Login

- **CPF**: apenas números ou formatado (000.000.000-00)
- **Data de nascimento**: dd/mm/yyyy ou ddmmyyyy (ex: 16091993 para 16/09/1993)

O site usa o campo `birthDate` no formato mm/dd/yyyy internamente; o scraper converte automaticamente.

## Configuração

### Variáveis de ambiente (.env)

```env
EDUCADVENTISTA_CPF=01596670207
EDUCADVENTISTA_DATA_NASCIMENTO=16091993
# Opcional: busca código PIX para cada parcela (mais lento)
EDUCADVENTISTA_BUSCAR_PIX=1
# Opcional: só processa parcelas com essa data de vencimento (dd/mm/yyyy)
EDUCADVENTISTA_VENCIMENTO=10/03/2026
```

### Agendamento

```env
SCHEDULER_EDUCADVENTISTA_ENABLED=1
SCHEDULER_EDUCADVENTISTA_CRON=0 7 * * *
```

Formato cron: `minuto hora dia_do_mes mes dia_da_semana` (ex: todo dia às 7h)

## Uso

### Sincronização manual

```bash
make sync-escola
```

### Via API

```bash
# Listar períodos
curl "http://localhost:8000/api/faturas?provedor=escola"

# Detalhes de um período
curl "http://localhost:8000/api/faturas/2026/3?provedor=escola"

# Forçar atualização
curl "http://localhost:8000/api/faturas/2026/3?provedor=escola&atualizar=true"

# Sincronizar
curl -X POST "http://localhost:8000/api/sync/run?provedor=escola"
```

## Fluxo do scraper

1. Acessa a página de login
2. Preenche CPF e data de nascimento
3. Clica em Entrar
4. Aguarda redirecionamento
5. Se houver carrossel de alunos, clica em "Parcelas" do primeiro
6. Seleciona localidade (se houver mais de uma)
7. Extrai parcelas da página (dados em JSON nos scripts)
8. Se `EDUCADVENTISTA_VENCIMENTO` estiver definido, filtra apenas parcelas com essa data
9. Para cada parcela (ou só as filtradas), clica em "Pagar" → "Ir para pagamento" → "Gerar código Pix" e extrai o PIX
10. Salva no banco (tabela `faturas_escola`)

## Dados extraídos

Cada parcela contém: ReferenceDate, DueDate, TotalToPay, Value, StatusPayment, Id, Number (boleto), BeneficiaryName, etc.

### Dados do modal PIX (quando EDUCADVENTISTA_BUSCAR_PIX=1)

Do modal "Gerar código Pix" são extraídos e salvos:

| Campo no banco | Descrição | Exemplo |
|----------------|-----------|---------|
| `valor` | Valor da parcela | 1089.00 |
| `nome_aluno` | Nome do aluno | Douglas Enrique da Silva Gonçalves |
| `data_validade_pix` | Validade do PIX | 05/03/2026 às 02:34 |
| `status_pix` | ativo ou expirado | ativo |
| `codigo_pix` | Código PIX copia e cola | 00020101021226850014br.gov.bcb.pix... |
| `qrcode_base64` | Imagem QR Code em base64 | data:image/png;base64,iVBORw0KGgo... |

### Migração do banco

Se a tabela `faturas_escola` já existia, execute para adicionar as colunas PIX:

```bash
make db-migrate-faturas-escola-pix
```
