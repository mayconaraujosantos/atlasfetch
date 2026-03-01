#!/usr/bin/env python3
"""
Configuração única do Gmail API (OAuth2).
Execute UMA VEZ para autorizar o acesso aos e-mails.
Salva credentials e token no banco (tabela gmail_oauth_config).
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))

from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 60)
    print("Configuração Gmail API - Automação sem senha de app")
    print("=" * 60)
    print()

    creds_path = os.path.join(_root, "credentials.json")

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
        from google_auth_oauthlib.flow import InstalledAppFlow
        from atlasfetch.infrastructure.persistence.database import (
            init_db,
            set_gmail_oauth_config,
        )
    except ImportError as e:
        print("Erro de import:", e)
        print("Instale: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    REDIRECT_PORT = 8080

    init_db()

    print("Abrindo navegador para autorização...")
    print("Faça login no Gmail e clique em 'Permitir' quando solicitado.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=REDIRECT_PORT)

    with open(creds_path, encoding="utf-8") as f:
        credentials_json = f.read()

    set_gmail_oauth_config(credentials_json=credentials_json, token_json=creds.to_json())

    print()
    print("Sucesso! Credentials e token salvos no banco (gmail_oauth_config).")
    print("O scraper agora pode ler e-mails automaticamente.")
    print("Não é necessário executar este script novamente.")
    print()
    print("Dica: pode remover credentials.json e token.json - os dados estão no banco.")


if __name__ == "__main__":
    main()
