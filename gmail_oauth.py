"""
Gmail API com OAuth2 - leitura de e-mails SEM senha de app.
Requer configuração única: credentials.json + autorização no navegador.
"""

import base64
import logging
import os
import re

logger = logging.getLogger(__name__)

# Escopo para ler e-mails (somente leitura)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Padrão para código de 6 dígitos
CODE_PATTERN = re.compile(r"\b(\d{6})\b")

# Palavras-chave para identificar e-mail de verificação
KEYWORDS = ["aegea", "aguas", "verifica", "código", "codigo", "microsoft", "b2clogin"]


def _get_credentials_path() -> str:
    """Caminho do arquivo credentials.json."""
    return os.path.join(os.path.dirname(__file__), "credentials.json")


def _get_token_path() -> str:
    """Caminho do arquivo token.json (salvo após autorização)."""
    return os.path.join(os.path.dirname(__file__), "token.json")


def _extract_code_from_text(text: str) -> str | None:
    """Extrai código de 6 dígitos do texto."""
    if not text:
        return None
    match = CODE_PATTERN.search(text)
    return match.group(1) if match else None


def _is_verification_email(subject: str, sender: str, snippet: str) -> bool:
    """Verifica se o e-mail parece ser de verificação."""
    text = f"{subject} {sender} {snippet}".lower()
    return any(kw in text for kw in KEYWORDS)


def fetch_verification_code_oauth(
    max_wait_seconds: int = 120,
    check_interval: int = 5,
) -> str | None:
    """
    Busca código de verificação via Gmail API (OAuth2).
    Não requer senha de app - apenas autorização única no navegador.

    Pré-requisito: executar `python setup_gmail_oauth.py` uma vez.
    """
    creds_path = _get_credentials_path()
    token_path = _get_token_path()

    if not os.path.exists(creds_path):
        logger.error(
            "Arquivo credentials.json não encontrado. "
            "Execute: python setup_gmail_oauth.py"
        )
        return None

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.error(
            "Instale as dependências: pip install google-auth-oauthlib google-api-python-client"
        )
        return None

    # Sem interação humana: token deve existir e ser válido
    if not os.path.exists(token_path):
        logger.error("token.json não encontrado. Execute: python setup_gmail_oauth.py")
        return None

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        else:
            logger.error("Token inválido. Execute: python setup_gmail_oauth.py")
            return None

    service = build("gmail", "v1", credentials=creds)

    import time
    start = time.time()
    while (time.time() - start) < max_wait_seconds:
        try:
            results = service.users().messages().list(
                userId="me",
                maxResults=15,
                q="newer_than:1h",  # E-mails da última hora
            ).execute()

            messages = results.get("messages", [])
            for msg_ref in reversed(messages):
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_ref["id"],
                    format="full",
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers.get("Subject", "")
                sender = headers.get("From", "")
                snippet = msg.get("snippet", "")

                if not _is_verification_email(subject, sender, snippet):
                    continue

                # Extrair corpo completo
                body = ""
                payload = msg.get("payload", {})
                if "parts" in payload:
                    for part in payload["parts"]:
                        if part.get("mimeType") == "text/plain":
                            data = part.get("body", {}).get("data")
                            if data:
                                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                                break
                        elif part.get("mimeType") == "text/html" and not body:
                            data = part.get("body", {}).get("data")
                            if data:
                                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                                body = re.sub(r"<[^>]+>", " ", html)
                else:
                    data = payload.get("body", {}).get("data")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

                text_to_search = body or snippet
                code = _extract_code_from_text(text_to_search)
                if code:
                    logger.info("Código de verificação encontrado via Gmail API")
                    return code

        except Exception as e:
            logger.debug("Erro Gmail API: %s", e)

        time.sleep(check_interval)

    logger.warning("Código não encontrado no tempo limite")
    return None
