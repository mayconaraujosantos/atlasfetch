#!/usr/bin/env python3
"""
Configuração única do Gmail API (OAuth2).
Execute este script UMA VEZ para autorizar o acesso aos e-mails.
Após isso, o scraper funcionará automaticamente sem senha de app.
"""

import os
import sys

# Adiciona o diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 60)
    print("Configuração Gmail API - Automação sem senha de app")
    print("=" * 60)
    print()

    creds_path = os.path.join(os.path.dirname(__file__), "credentials.json")

    if not os.path.exists(creds_path):
        print("ERRO: credentials.json não encontrado!")
        print()
        print("Passos para obter o arquivo:")
        print("1. Acesse: https://console.cloud.google.com/")
        print("2. Crie um projeto (ou use existente)")
        print("3. Ative a Gmail API: APIs e Serviços > Biblioteca > Gmail API")
        print("4. Crie credenciais: APIs e Serviços > Credenciais")
        print("   - Tipo: Aplicativo de computador")
        print("   - Baixe o JSON e salve como 'credentials.json' nesta pasta")
        print("5. Tela de consentimento: adicione seu e-mail em 'Usuários de teste'")
        print()
        print("Documentação: https://developers.google.com/gmail/api/quickstart/python")
        sys.exit(1)

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Instale as dependências: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    token_path = os.path.join(os.path.dirname(__file__), "token.json")

    # Porta fixa para evitar redirect_uri_mismatch - adicione no Google Cloud Console
    REDIRECT_PORT = 8080

    print("Abrindo navegador para autorização...")
    print("Faça login no Gmail e clique em 'Permitir' quando solicitado.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=REDIRECT_PORT)

    with open(token_path, "w") as f:
        f.write(creds.to_json())

    print()
    print("Sucesso! Token salvo em token.json")
    print("O scraper agora pode ler e-mails automaticamente.")
    print("Não é necessário executar este script novamente.")


if __name__ == "__main__":
    main()
