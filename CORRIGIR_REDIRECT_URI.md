# Corrigir Erro 400: redirect_uri_mismatch

Se você vê **"Acesso bloqueado: a solicitação desse app é inválida"** com **Erro 400: redirect_uri_mismatch**, siga estes passos:

---

## Passo a passo

### 1. Abra o Google Cloud Console

https://console.cloud.google.com/

### 2. Vá em Credenciais

Menu lateral → **APIs e Serviços** → **Credenciais**

### 3. Clique no seu cliente OAuth

Na lista, clique no **nome** do "ID do cliente OAuth" (não no ícone de chave).

### 4. Adicione os URIs de redirecionamento

Role até **"URIs de redirecionamento autorizados"** (ou "Authorized redirect URIs").

Clique em **"+ ADICIONAR URI"** e adicione **um por vez**:

| URI (copie exatamente) |
|------------------------|
| `http://localhost:8080/` |
| `http://127.0.0.1:8080/` |

**Atenção:**
- Use `http` (não `https`)
- Use `localhost` (não `127.0.0.1` no primeiro – adicione os dois)
- Inclua a **barra no final** (`/`)
- Porta é **8080**

### 5. Salvar

Clique no botão **SALVAR** no final da página.

### 6. Aguardar

Espere 1–2 minutos e execute novamente:

```bash
python setup_gmail_oauth.py
```

---

## Seu credentials.json

Seu arquivo é do tipo **"web"** (Aplicativo da Web). Para esse tipo, os URIs de redirecionamento são **obrigatórios** e precisam estar configurados exatamente como acima.
