# API para consumo por IA

Esta API foi desenhada para ser consumida por assistentes de IA. A IA pode interpretar comandos em linguagem natural e mapear para os endpoints abaixo.

## Mapeamento: linguagem natural → API

| Usuário diz | Ação da IA |
|-------------|------------|
| "Quero a conta de luz do mês 2" | `GET /api/faturas/2026/2?provedor=luz` |
| "Mostra minhas faturas de água" | `GET /api/faturas?provedor=aguas` |
| "Quais faturas tenho?" | `GET /api/faturas?provedor=todos` |
| "Conta de água de janeiro" | `GET /api/faturas/2026/1?provedor=aguas` |
| "Sincronizar minhas contas" | `POST /api/sync/run?provedor=todos` |
| "Atualizar conta de luz" | `POST /api/sync/run?provedor=luz` |

## Endpoints

### Listar períodos

```
GET /api/faturas?provedor=aguas|luz|todos
```

- **aguas** (padrão): faturas de água
- **luz**: faturas de energia
- **todos**: ambas (cada item inclui `provedor`)

### Detalhes de uma fatura

```
GET /api/faturas/{ano}/{mes}?provedor=aguas|luz
```

- **atualizar=true**: força nova busca (água: login+API; luz: sync e salva)

### Sincronizar (buscar dados atualizados)

```
POST /api/sync/run?provedor=aguas|luz|todos
```

- **aguas**: login Águas de Manaus, busca débitos
- **luz**: usa token salvo, busca consumos Amazonas Energia
- **todos**: executa ambos

## Fluxo recomendado para a IA

1. **"Quero conta de luz do mês X"**
   - `GET /api/faturas?provedor=luz` → verifica se há períodos
   - `GET /api/faturas/{ano}/{mes}?provedor=luz` → retorna detalhes
   - Se 404: `POST /api/sync/run?provedor=luz` e tentar novamente

2. **"Sincronizar tudo"**
   - `POST /api/sync/run?provedor=todos`
   - Resposta indica sucesso/erro por provedor

3. **"Quais contas tenho?"**
   - `GET /api/faturas?provedor=todos`
   - Resposta lista períodos de água e luz

## Base URL

```
http://localhost:8000
```

Em produção, use a URL do serviço (ex: Railway).

## Visão futura: reCAPTCHA automático

O login da Amazonas Energia usa reCAPTCHA. Hoje o token é obtido via `make setup-amazonas-energia` (login manual uma vez). Para automação total:

- **Opção 1:** IA com visão (GPT-4V, Claude) – captura screenshot do captcha, envia para a IA, interpreta resposta e simula cliques. Permite resolver reCAPTCHA sem serviços pagos.
- **Opção 2:** 2Captcha ou similar (pago).
- **Opção 3:** API oficial da Amazonas Energia, se disponível no futuro.
