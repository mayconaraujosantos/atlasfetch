# API para App Mobile (React Native)

Endpoints otimizados para exibir faturas, valores, datas e códigos de pagamento.

## Base URL

```
http://localhost:8000
# ou sua URL em produção
```

## Endpoints

### 1. Listar períodos disponíveis

```
GET /api/faturas
```

Retorna os períodos (mês/ano) que têm faturas. Use para exibir a lista inicial no app.

**Resposta:**
```json
{
  "periodos": [
    {
      "ano": 2026,
      "mes": 2,
      "periodo": "02/2026",
      "valorTotal": 62.57,
      "quantidadeDebitos": 1,
      "existeDebitoVencido": false
    },
    {
      "ano": 2026,
      "mes": 1,
      "periodo": "01/2026",
      "valorTotal": 62.61,
      "quantidadeDebitos": 1,
      "existeDebitoVencido": true
    }
  ]
}
```

### 2. Detalhes de uma fatura (período)

```
GET /api/faturas/{ano}/{mes}
GET /api/faturas/2026/2
```

**Query params:**
- `atualizar` (boolean, default: false) – Se `true`, força nova consulta à API (login + busca). Use com moderação.

**Resposta:**
```json
{
  "resumo": {
    "periodo": "02/2026",
    "ano": 2026,
    "mes": 2,
    "valorTotal": 62.57,
    "quantidadeDebitos": 1,
    "existeDebitoVencido": false,
    "consultadoEm": "2026-02-28T22:00:00"
  },
  "debitos": [
    {
      "id": 159900829,
      "referencia": "02/2026",
      "valor": 62.57,
      "dataVencimento": "2026-03-10T00:00:00",
      "codigoBarras": "82690000000000000000000000000000000000000000000",
      "codigoPix": "00020126580014br.gov.bcb.pix...",
      "status": "Em dia",
      "situacaoPagamento": "Aberto"
    }
  ]
}
```

**Campos para o app:**
- `valor` – valor da fatura (R$)
- `dataVencimento` – data de vencimento (ISO)
- `codigoBarras` – código de barras para pagamento
- `codigoPix` – código PIX (copia e cola)
- `status` – ex: "Atrasada", "Em dia"

## Fluxo sugerido no React Native

1. **Tela inicial:** `GET /api/faturas` → lista de períodos
2. **Ao tocar em um período:** `GET /api/faturas/{ano}/{mes}` → resumo + débitos
3. **Exibir:** valor, data, botão "Copiar PIX", botão "Ver código de barras"

## Compatibilidade

- `GET /api/faturas/{ano}/{mes}/historico` – mantido para compatibilidade (formato antigo)
