"""
Gmail API com OAuth2 - leitura de e-mails SEM senha de app.
Lê credentials e token do banco (tabela gmail_oauth_config) ou dos arquivos (fallback).
"""

import base64
import json
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


def _get_project_root() -> str:
    """Raiz do projeto (onde ficam credentials.json e token.json)."""
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )


def _get_credentials_path() -> str:
    """Caminho do arquivo credentials.json (na raiz do projeto)."""
    return os.path.join(_get_project_root(), "credentials.json")


def _get_token_path() -> str:
    """Caminho do arquivo token.json (na raiz do projeto)."""
    return os.path.join(_get_project_root(), "token.json")


def _get_credentials_and_token() -> tuple[str | None, str | None]:
    """
    Obtém credentials_json e token_json.
    Ordem: 1) banco, 2) arquivos.
    """
    try:
        from atlasfetch.infrastructure.persistence.database import get_gmail_oauth_config

        creds_db, token_db = get_gmail_oauth_config()
        if creds_db and token_db:
            return (creds_db, token_db)
    except Exception as e:
        logger.debug("Falha ao ler Gmail OAuth do banco: %s", e)

    # Fallback: arquivos
    creds_path = _get_credentials_path()
    token_path = _get_token_path()
    creds_json = None
    token_json = None
    if os.path.exists(creds_path):
        with open(creds_path, encoding="utf-8") as f:
            creds_json = f.read()
    if os.path.exists(token_path):
        with open(token_path, encoding="utf-8") as f:
            token_json = f.read()
    return (creds_json, token_json)


def has_gmail_oauth_config() -> bool:
    """Verifica se credentials e token estão disponíveis (banco ou arquivos)."""
    creds, token = _get_credentials_and_token()
    return bool(creds and token)


def _save_token_to_store(token_json: str) -> None:
    """Salva token no banco ou no arquivo."""
    try:
        from atlasfetch.infrastructure.persistence.database import set_gmail_oauth_config

        set_gmail_oauth_config(token_json=token_json)
        logger.debug("Token Gmail OAuth salvo no banco")
    except Exception as e:
        logger.debug("Falha ao salvar token no banco: %s", e)
        token_path = _get_token_path()
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(token_json)


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
    Lê credentials e token do banco ou dos arquivos.
    Não requer senha de app - apenas autorização única no navegador.

    Pré-requisito: executar `make setup-gmail` uma vez.
    """
    creds_json, token_json = _get_credentials_and_token()

    if not creds_json:
        logger.error(
            "Credentials não encontrados (banco ou arquivo). "
            "Execute: make setup-gmail"
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

    if not token_json:
        logger.error("Token não encontrado (banco ou arquivo). Execute: make setup-gmail")
        return None

    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token_to_store(creds.to_json())
        else:
            logger.error("Token inválido. Execute: make setup-gmail")
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
