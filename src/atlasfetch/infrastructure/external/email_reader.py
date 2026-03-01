"""
Módulo para ler o código de verificação enviado por e-mail (Águas de Manaus / Aegea).
Conecta ao Gmail via IMAP e extrai o código automaticamente.
"""

import imaplib
import email
import logging
import re
import os
import time
from email.header import decode_header

logger = logging.getLogger(__name__)


# Remetentes prováveis do código de verificação (Aegea/Águas/B2C/Microsoft)
SENDER_KEYWORDS = ["aegea", "aguas", "noreply", "nao-responda", "microsoft", "b2clogin", "azure"]

# Padrões para extrair código (6 dígitos é o mais comum em 2FA)
CODE_PATTERNS = [
    r"\b(\d{6})\b",           # 6 dígitos
    r"c[óo]digo[:\s]+(\d{4,8})",
    r"c[óo]digo de verifica[çc][ãa]o[:\s]+(\d{4,8})",
    r"seu c[óo]digo[:\s]+(\d{4,8})",
    r"verification code[:\s]+(\d{4,8})",
    r"(\d{4,8})",
]


def decode_mime_header(header: str) -> str:
    """Decodifica header MIME (subject, from, etc)."""
    if not header:
        return ""
    decoded_parts = decode_header(header)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def extract_code_from_text(text: str) -> str | None:
    """Extrai o código de verificação do texto do e-mail."""
    if not text:
        return None
    text = text.replace("\r\n", " ").replace("\n", " ")
    for pattern in CODE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def get_email_body(msg: email.message.Message) -> str:
    """Extrai o corpo do e-mail (text/plain ou text/html)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
                except Exception:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Remove tags HTML para buscar o código
                    body += re.sub(r"<[^>]+>", " ", html)
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        except Exception:
            pass
    return body


def is_verification_email(msg: email.message.Message) -> bool:
    """Verifica se o e-mail parece ser de verificação (Aegea/Águas)."""
    from_header = msg.get("From", "") or ""
    subject = msg.get("Subject", "") or ""
    from_decoded = decode_mime_header(from_header).lower()
    subject_decoded = decode_mime_header(subject).lower()
    keywords = SENDER_KEYWORDS + ["verifica", "código", "codigo"]
    return any(kw in from_decoded or kw in subject_decoded for kw in keywords)


def fetch_verification_code(
    email_user: str | None = None,
    email_password: str | None = None,
    folder: str = "INBOX",
    max_wait_seconds: int = 120,
    check_interval: int = 5,
) -> str | None:
    """
    Conecta ao Gmail via IMAP, busca e-mails recentes e extrai o código de verificação.

    Args:
        email_user: E-mail (default: GMAIL_USER env)
        email_password: Senha de app (default: GMAIL_APP_PASSWORD env)
        folder: Pasta IMAP (default: INBOX)
        max_wait_seconds: Tempo máximo de espera pelo e-mail
        check_interval: Intervalo entre verificações em segundos

    Returns:
        Código de verificação (string) ou None se não encontrar
    """
    user = email_user or os.environ.get("GMAIL_USER")
    password = email_password or os.environ.get("GMAIL_APP_PASSWORD")

    if not user or not password:
        logger.info("GMAIL_USER/GMAIL_APP_PASSWORD não configurados - use entrada manual")
        return None

    logger.info(
        "Aguardando código de verificação no e-mail (máx. %ds, intervalo %ds)",
        max_wait_seconds,
        check_interval,
    )
    start = time.time()

    while (time.time() - start) < max_wait_seconds:
        try:
            logger.debug("Conectando ao Gmail IMAP...")
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(user, password)
            mail.select(folder)

            # Busca: primeiro UNSEEN, se vazio busca ALL (e-mail pode já ter sido lido)
            status, messages = mail.search(None, "UNSEEN")
            uid_list = messages[0].split() if status == "OK" else []

            if not uid_list:
                status, messages = mail.search(None, "ALL")
                uid_list = messages[0].split() if status == "OK" else []
                if uid_list:
                    logger.debug("Nenhum não lido - buscando nos %d e-mails recentes", len(uid_list))

            if uid_list:
                # Pega os 15 mais recentes (ordem: mais novo primeiro)
                uids_to_check = list(reversed(uid_list[-15:]))
                logger.debug("Verificando %d e-mail(s)", len(uids_to_check))
                for uid in uids_to_check:
                    status, data = mail.fetch(uid, "(RFC822)")
                    if status != "OK" or not data:
                        continue
                    for response_part in data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            if is_verification_email(msg):
                                body = get_email_body(msg)
                                code = extract_code_from_text(body)
                                if code:
                                    logger.info("Código de verificação encontrado no e-mail")
                                    mail.logout()
                                    return code

            mail.logout()
        except imaplib.IMAP4.error as e:
            err_str = str(e).lower()
            if "application-specific" in err_str or "app password" in err_str:
                raise RuntimeError(
                    "Use SENHA DE APP (não a senha normal): "
                    "https://myaccount.google.com/apppasswords"
                ) from e
            logger.warning("Erro IMAP: %s", str(e)[:80])
            return None
        except Exception as e:
            logger.debug("Erro ao verificar e-mail (tentando novamente): %s", e)

        elapsed = int(time.time() - start)
        logger.debug("Nenhum código ainda (elapsed=%ds) - aguardando %ds", elapsed, check_interval)
        time.sleep(check_interval)

    logger.warning("Timeout: código de verificação não encontrado no tempo limite")
    return None


if __name__ == "__main__":
    # Teste rápido
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s | %(name)s | %(message)s")

    code = fetch_verification_code(max_wait_seconds=30)
    if code:
        print(f"Código encontrado: {code}")
        sys.exit(0)
    else:
        print("Nenhum código encontrado no tempo limite.")
        sys.exit(1)
