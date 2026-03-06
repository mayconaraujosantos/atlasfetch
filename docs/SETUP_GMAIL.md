# Automação do código de verificação (Gmail)

**Zero interação humana.** O scraper lê o código automaticamente.

---

## Opção 1: IMAP (recomendado – só .env)

**Sem setup script.** Apenas configurar o `.env`:

1. Acesse https://myaccount.google.com/apppasswords
2. Crie uma senha de app (ex.: "Atlasfetch")
3. No `.env`:
   ```
   GMAIL_USER=seu@email.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```

Pronto. Não use a senha normal do Gmail – use a senha de app.

---

## Opção 2: Gmail API com OAuth2

**Não requer senha de app.** Configuração única (~5 min).

### Como obter o credentials.json

#### 1. Acessar o Google Cloud Console

Abra no navegador: **https://console.cloud.google.com/**

Faça login com a conta Gmail que receberá os códigos de verificação.

---

#### 2. Criar um projeto

- Clique no seletor de projeto (topo da página, ao lado de "Google Cloud")
- Clique em **"Novo projeto"**
- Nome: ex. `atlasfetch` ou `scraper-aguas`
- Clique em **"Criar"**
- Selecione o projeto criado

---

#### 3. Ativar a Gmail API

- Menu lateral: **APIs e Serviços** → **Biblioteca**
- Busque: `Gmail API`
- Clique em **"Gmail API"**
- Clique em **"Ativar"**

---

#### 4. Configurar a tela de consentimento OAuth

- Menu lateral: **APIs e Serviços** → **Tela de consentimento OAuth**
- Se pedir, escolha **"Externo"** → Avançar
- Preencha:
  - **Nome do app**: ex. `Atlasfetch`
  - **E-mail de suporte**: seu e-mail
- Clique em **"Salvar e continuar"**
- Em **Escopos**: clique em **"Adicionar ou remover escopos"**
  - Busque `gmail.readonly` e marque
  - Salvar e continuar
- Em **Usuários de teste**: clique em **"+ ADICIONAR USUÁRIOS"**
  - Adicione o e-mail que receberá os códigos (ex. `mv.maycon.araujo.santos@gmail.com`)
  - **Obrigatório** – sem isso você verá "Erro 403: access_denied"
  - Salvar e continuar

---

#### 5. Criar as credenciais OAuth

- Menu lateral: **APIs e Serviços** → **Credenciais**
- Clique em **"+ Criar credenciais"**
- Selecione **"ID do cliente OAuth"**
- Tipo de aplicativo: **"Aplicativo de computador"**
- Nome: ex. `Atlasfetch Desktop`
- Clique em **"Criar"**
- Na janela que abrir, clique em **"Fazer download do JSON"**

**OBRIGATÓRIO – corrigir erro redirect_uri_mismatch:**

1. Em **Credenciais**, clique no **ID do cliente OAuth** (o que você criou)
2. Em **"URIs de redirecionamento autorizados"** (Authorized redirect URIs):
   - Clique em **"+ ADICIONAR URI"**
   - Cole **exatamente** (copie e cole, sem alterar):
     ```
     http://localhost:8080/
     ```
   - Clique em **"+ ADICIONAR URI"** de novo e adicione:
     ```
     http://127.0.0.1:8080/
     ```
3. **Salvar** (botão no final da página)
4. Aguarde 1–2 minutos para a alteração propagar

---

#### 6. Salvar o arquivo

- O download virá com nome similar a `client_secret_xxx.apps.googleusercontent.com.json`
- **Renomeie** para: `credentials.json`
- **Mova** para a pasta do projeto (mesmo nível que `main.py`)

```
atlasfetch/
├── credentials.json   ← aqui
├── main.py
├── scraper.py
└── ...
```

---

#### 7. Autorizar (uma vez)

```bash
pip install -r requirements.txt
python setup_gmail_oauth.py
```

- O navegador abrirá
- Faça login no Gmail (se necessário)
- Clique em **"Permitir"** ou **"Allow"**
- O arquivo `token.json` será criado automaticamente

---

#### 8. Pronto

Execuções futuras são 100% automáticas. Não é necessário repetir a autorização.

---

## Opção 2: IMAP com senha de app

Requer conta com 2FA e senha de app.

1. Crie senha de app: https://myaccount.google.com/apppasswords
2. No `.env`:
   ```
   GMAIL_USER=seu@email.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```

---

## Resumo

| Método      | Setup script? | Configuração |
|------------|----------------|--------------|
| IMAP       | Não            | Só .env (GMAIL_USER + GMAIL_APP_PASSWORD) |
| Gmail API  | Sim (make setup-gmail) | credentials.json + token.json |

---

## Erro: "Application-specific password required"

Se você vê esse erro ao usar o scheduler ou `make run`:

1. **Usando OAuth (recomendado):** Execute `make setup-gmail` e garanta que `credentials.json` e `token.json` estejam na raiz do projeto.
2. **Remova do .env:** Se estiver usando OAuth, **não defina** `GMAIL_USER` nem `GMAIL_APP_PASSWORD`. Eles fazem o scraper tentar IMAP, que exige senha de app.
3. **Usando IMAP:** Se preferir IMAP, crie uma senha de app em https://myaccount.google.com/apppasswords e use em `GMAIL_APP_PASSWORD` (não use a senha normal do Gmail).
