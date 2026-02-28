# Corrigir Erro 403: access_denied

**"O app atlasfetch não concluiu o processo de verificação do Google"**

O app está em **modo de testes**. Apenas e-mails adicionados como **testadores** podem usar.

---

## Solução: adicionar seu e-mail como testador

### 1. Abra o Google Cloud Console

https://console.cloud.google.com/

### 2. Vá na Tela de consentimento OAuth

Menu lateral → **APIs e Serviços** → **Tela de consentimento OAuth**

### 3. Adicione seu e-mail em "Usuários de teste"

- Role até a seção **"Usuários de teste"** (Test users)
- Clique em **"+ ADICIONAR USUÁRIOS"**
- Digite: `mv.maycon.araujo.santos@gmail.com`
- Clique em **"Adicionar"** ou **"Salvar"**

### 4. Salvar

Clique em **"Salvar e continuar"** se houver.

### 5. Testar novamente

```bash
python setup_gmail_oauth.py
```

---

## Resumo

| Modo do app | Quem pode usar |
|-------------|----------------|
| **Testando** | Apenas e-mails em "Usuários de teste" |
| **Em produção** | Qualquer conta Google (requer verificação do Google) |

Para uso pessoal, manter em **Testando** e adicionar seu e-mail é suficiente.
