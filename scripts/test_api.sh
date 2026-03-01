#!/bin/bash
# Testes da API via curl
# Pré-requisito: API rodando (make api)

BASE="${1:-http://127.0.0.1:8000}"

echo "=== Testando API em $BASE ==="
echo ""

echo "1. GET /health"
resp=$(curl -s "$BASE/health")
echo "   Response: $resp"
echo "$resp" | grep -q '"status":"ok"' && echo "   OK" || echo "   FALHOU"
echo ""

echo "2. GET /api/faturas (listar períodos)"
resp=$(curl -s -w "\n%{http_code}" "$BASE/api/faturas")
code=$(echo "$resp" | tail -n1)
body=$(echo "$resp" | sed '$d')
echo "   Status: $code"
if [ "$code" = "200" ]; then
  echo "   OK"
  echo "   Body: $(echo "$body" | head -c 300)..."
else
  echo "   Response: $body"
  echo "   FALHOU"
fi
echo ""

echo "3. GET /api/faturas/2026/2 (detalhes do período)"
resp=$(curl -s -w "\n%{http_code}" "$BASE/api/faturas/2026/2")
code=$(echo "$resp" | tail -n1)
body=$(echo "$resp" | sed '$d')
echo "   Status: $code"
if [ "$code" = "200" ]; then
  echo "   OK - resumo + débitos"
  echo "$body" | python3 -m json.tool 2>/dev/null | head -30 || echo "$body" | head -c 400
  echo "..."
elif [ "$code" = "404" ]; then
  echo "   OK - nenhuma fatura no banco"
else
  echo "   Response: $body"
  echo "   FALHOU"
fi
echo ""

echo "4. GET /api/faturas/2026/2?atualizar=false (do banco)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/faturas/2026/2?atualizar=false")
echo "   Status: $code (esperado: 200 ou 404)"
[ "$code" = "200" ] || [ "$code" = "404" ] && echo "   OK" || echo "   FALHOU"
echo ""

echo "5. GET /api/faturas/1999/1 (sem dados)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/faturas/1999/1")
echo "   Status: $code (esperado: 404)"
[ "$code" = "404" ] && echo "   OK" || echo "   FALHOU"
echo ""

echo "6. GET /api/faturas/2026/2/historico (legado)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/faturas/2026/2/historico")
echo "   Status: $code (esperado: 200 ou 404)"
[ "$code" = "200" ] || [ "$code" = "404" ] && echo "   OK" || echo "   FALHOU"
echo ""

echo "7. POST /api/sync/run"
resp=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/sync/run")
code=$(echo "$resp" | tail -n1)
body=$(echo "$resp" | sed '$d')
echo "   Status: $code"
if [ "$code" = "200" ]; then
  echo "   OK - sync executado"
  echo "   Response: $body"
else
  echo "   Response: $body"
  echo "   (500 esperado se credenciais não configuradas)"
fi
echo ""

echo "8. GET /docs (Swagger)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/docs")
echo "   Status: $code (esperado: 200)"
[ "$code" = "200" ] && echo "   OK" || echo "   FALHOU"
echo ""

echo "9. GET /openapi.json"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/openapi.json")
echo "   Status: $code (esperado: 200)"
[ "$code" = "200" ] && echo "   OK" || echo "   FALHOU"
echo ""

echo "=== Fim dos testes ==="
echo ""
echo "Comandos curl manuais:"
echo "  curl $BASE/health"
echo "  curl $BASE/api/faturas"
echo "  curl \"$BASE/api/faturas/2026/2\""
echo "  curl \"$BASE/api/faturas/2026/2?atualizar=true\""
echo "  curl -X POST $BASE/api/sync/run"
