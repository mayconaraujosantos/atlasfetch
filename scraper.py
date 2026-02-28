"""
Scraper para Águas de Manaus - login via Azure B2C e coleta de dados de faturas.
"""

import logging
import os
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from email_reader import fetch_verification_code

try:
    from gmail_oauth import fetch_verification_code_oauth
except ImportError:
    fetch_verification_code_oauth = None

load_dotenv()

logger = logging.getLogger(__name__)

# URLs e constantes
LOGIN_URL = "https://cliente.aguasdemanaus.com.br/home"
API_BASE = "https://api.aegea.com.br/external/agencia-virtual/app/v1"
API_TENANT_ID = "a3bc65bb-225b-0920-e053-02a0c40a5880"
API_SUBSCRIPTION_KEY = "f0d0a49417c040eab2965e02579b15c2"

# Seletores do formulário B2C
SELECTOR_CPF = "#signInName"
SELECTOR_SENHA = "#password"
SELECTOR_ENTRAR = "#next"

# Modal 2FA - estrutura real do B2C (data-name="SelfAsserted", form attributeVerification)
SELECTOR_MODAL_2FA = "#api[data-name='SelfAsserted']"
SELECTOR_FORM_VERIFICATION = "#attributeVerification"

# Input do código - id exato do HTML do modal
SELECTOR_VERIFICATION_INPUT = "#verificationCode"

# Botão "Enviar código de verificação" - clicar PRIMEIRO para disparar o envio do e-mail
SELECTOR_SEND_CODE_BUTTON = "#emailVerificationControl_but_send_code"

# Botão "Verificar código" - clicar após preencher o código no input
SELECTOR_VERIFY_BUTTON = "#emailVerificationControl_but_verify_code"


@dataclass
class ScraperResult:
    """Resultado do scraper com token e dados do cliente."""

    access_token: str
    matricula: str | None = None
    sequencial_responsavel: str | None = None
    zona_ligacao: str | None = None


def _get_verification_code() -> str:
    """
    Obtém o código de verificação automaticamente (sem interação humana).
    Ordem: Gmail API (OAuth2) > IMAP (senha de app).
    """
    codigo = None

    # 1. Gmail API com OAuth2 - SEM senha de app
    creds_path = os.path.join(os.path.dirname(__file__), "credentials.json")
    token_path = os.path.join(os.path.dirname(__file__), "token.json")
    if os.path.exists(creds_path) and os.path.exists(token_path) and fetch_verification_code_oauth:
        try:
            codigo = fetch_verification_code_oauth(max_wait_seconds=120, check_interval=3)
        except Exception as e:
            logger.debug("Gmail API: %s", e)

    # 2. IMAP (requer GMAIL_APP_PASSWORD)
    if not codigo and os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"):
        try:
            codigo = fetch_verification_code(max_wait_seconds=120, check_interval=3)
        except (ValueError, RuntimeError) as e:
            logger.debug("IMAP: %s", e)

    if not codigo:
        raise RuntimeError(
            "Automação do código de verificação falhou. "
            "Configure: python setup_gmail_oauth.py (uma vez) ou GMAIL_APP_PASSWORD no .env. "
            "Ver SETUP_GMAIL.md"
        )

    return codigo


def _capture_token_from_request(url: str, headers: dict) -> str | None:
    """Extrai o Bearer token da URL e headers de uma requisição à API Aegea."""
    if "api.aegea.com.br" not in url:
        return None
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def login(
    cpf: str | None = None,
    senha: str | None = None,
    headless: bool = True,
    timeout_ms: int = 60000,
) -> ScraperResult:
    """
    Realiza login no site Águas de Manaus e retorna o token de acesso.

    Args:
        cpf: CPF do usuário (default: AGUAS_CPF ou variável de ambiente)
        senha: Senha (default: AGUAS_SENHA)
        headless: Executar navegador em modo invisível
        timeout_ms: Timeout para operações em ms

    Returns:
        ScraperResult com access_token e dados do cliente (quando disponíveis)
    """
    cpf = cpf or os.environ.get("AGUAS_CPF")
    senha = senha or os.environ.get("AGUAS_SENHA")

    if not cpf or not senha:
        raise ValueError("Defina AGUAS_CPF e AGUAS_SENHA (variáveis de ambiente ou parâmetros)")

    logger.info("Iniciando login - CPF: %s***", cpf[:4] if len(cpf) > 4 else "****")
    logger.debug("headless=%s, timeout=%dms", headless, timeout_ms)

    captured_token: str | None = None
    captured_matricula: str | None = None
    captured_sequencial: str | None = None
    captured_zona: str | None = None

    def handle_request(request):
        nonlocal captured_token, captured_matricula, captured_sequencial, captured_zona
        url = request.url
        headers = request.headers

        token = _capture_token_from_request(url, headers)
        if token:
            captured_token = token
            logger.debug("Token capturado de requisição para: %s", url[:80])

        # Extrair matricula, sequencial, zona da URL da API
        if "api.aegea.com.br" in url and "matricula" in url:
            match = re.search(r"matricula=(\d+)", url)
            if match:
                captured_matricula = match.group(1)
            match = re.search(r"sequencialResponsavel=(\d+)", url)
            if match:
                captured_sequencial = match.group(1)
            match = re.search(r"zonaLigacao=(\d+)", url)
            if match:
                captured_zona = match.group(1)
            if captured_matricula:
                logger.debug(
                    "Dados capturados da URL: matricula=%s, sequencial=%s, zona=%s",
                    captured_matricula,
                    captured_sequencial,
                    captured_zona,
                )

    with sync_playwright() as p:
        logger.info("Iniciando navegador Chromium (headless=%s)", headless)
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
        )
        page = context.new_page()

        page.on("request", handle_request)

        try:
            logger.info("Acessando %s", LOGIN_URL)
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=timeout_ms)
            logger.debug("Página carregada")
        except PlaywrightTimeout:
            logger.warning("Timeout ao carregar página (pode ter carregado parcialmente)")

        # Preencher login
        logger.info("Aguardando formulário de login...")
        page.wait_for_selector(SELECTOR_CPF, timeout=timeout_ms)
        page.fill(SELECTOR_CPF, cpf)
        page.fill(SELECTOR_SENHA, senha)
        logger.info("Credenciais preenchidas, clicando em Entrar")
        page.click(SELECTOR_ENTRAR)

        # Aguardar modal 2FA (data-name="SelfAsserted" = formulário de verificação)
        logger.info("Aguardando modal de verificação 2FA (site envia código por e-mail)...")
        time.sleep(5)  # Tempo para o site enviar o e-mail e exibir o modal
        logger.info("URL após login: %s", page.url)

        # 1. Esperar #api[data-name='SelfAsserted'] - modal de verificação
        try:
            page.wait_for_selector(SELECTOR_MODAL_2FA, timeout=timeout_ms)
            logger.info("Modal 2FA encontrado (#api SelfAsserted)")
        except PlaywrightTimeout:
            logger.warning("Modal 2FA não encontrado - tentando input diretamente")

        # 2. Clicar em "Enviar código de verificação" para disparar o envio do e-mail
        send_code_clicked = False
        try:
            # Tentar por ID primeiro
            send_btn = page.wait_for_selector(SELECTOR_SEND_CODE_BUTTON, timeout=8000)
            if send_btn:
                logger.info("Clicando em 'Enviar código de verificação'...")
                send_btn.click(force=True)  # force=True caso esteja oculto por CSS
                send_code_clicked = True
                time.sleep(5)  # Aguardar e-mail ser enviado
        except PlaywrightTimeout:
            # Tentar por texto do botão
            try:
                send_btn = page.get_by_role("button", name="Enviar código de verificação")
                if send_btn.count() > 0:
                    logger.info("Clicando em 'Enviar código de verificação' (por texto)...")
                    send_btn.first.click(force=True)
                    send_code_clicked = True
                    time.sleep(5)
            except Exception:
                pass

        if not send_code_clicked:
            logger.info("Botão 'Enviar código' não encontrado - código pode ser enviado automaticamente")

        # 3. Esperar campo #verificationCode
        verification_input = None
        try:
            verification_input = page.wait_for_selector(
                SELECTOR_VERIFICATION_INPUT, timeout=15000
            )
            if verification_input and verification_input.is_visible():
                logger.info("Campo de código encontrado (#verificationCode)")
        except PlaywrightTimeout:
            logger.debug("Campo #verificationCode não encontrado")

        if verification_input and verification_input.is_visible():
            # 4. Obter código automaticamente (Gmail API ou IMAP)
            codigo = _get_verification_code()
            logger.info("Código de verificação recebido e preenchido")
            verification_input.fill(codigo)

            # Clicar em "Verificar código" (#emailVerificationControl_but_verify_code)
            verify_btn = page.query_selector(SELECTOR_VERIFY_BUTTON)
            if verify_btn and verify_btn.is_visible():
                logger.info("Clicando em 'Verificar código'")
                verify_btn.click()
            else:
                logger.debug("Botão 'Verificar código' não visível - tentando Enter")
                page.keyboard.press("Enter")
        else:
            # Modo descoberta: salvar HTML para identificar estrutura do modal
            if os.environ.get("DEBUG_MODAL") == "1":
                debug_dir = os.path.join(os.path.dirname(__file__), "debug")
                os.makedirs(debug_dir, exist_ok=True)
                html_path = os.path.join(debug_dir, "pagina_2fa.html")
                try:
                    html = page.content()
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    page.screenshot(path=os.path.join(debug_dir, "pagina_2fa.png"))
                    logger.warning(
                        "DEBUG_MODAL=1: HTML e screenshot salvos em debug/ - "
                        "inspecione para encontrar ID/class do modal de verificação"
                    )
                except Exception as e:
                    logger.debug("Erro ao salvar debug: %s", e)

            # Log possível mensagem de erro na página (ajuda no diagnóstico)
            try:
                error_el = page.query_selector(".error.pageLevel p, .error.itemLevel p, [role='alert']")
                if error_el and error_el.is_visible():
                    error_text = error_el.inner_text()
                    if error_text.strip():
                        logger.warning("Possível erro na página: %s", error_text.strip()[:200])
            except Exception:
                pass
            logger.info("2FA não detectado - prosseguindo (URL: %s)", page.url)

        # Aguardar redirecionamento e chamadas à API (para capturar token)
        try:
            logger.info("Aguardando redirecionamento pós-login...")
            page.wait_for_url(
                lambda url: "validar-matricula" in str(url) or "cliente.aguasdemanaus" in str(url),
                timeout=timeout_ms,
            )
            logger.debug("URL atual: %s", page.url)
        except PlaywrightTimeout:
            logger.warning("Timeout aguardando redirecionamento (URL atual: %s)", page.url)

        # Dar tempo para a página fazer chamadas à API
        logger.info("Aguardando captura do token nas requisições...")
        for i in range(20):
            if captured_token:
                logger.info("Token capturado após %d segundos", i)
                break
            time.sleep(1)

        # Tentar extrair token do localStorage (fallback - MSAL armazena lá)
        if not captured_token:
            logger.info("Token não capturado em requisições - tentando localStorage...")
            try:
                token_data = page.evaluate(
                    """
                    () => {
                        const keys = Object.keys(localStorage).filter(k => 
                            k.includes('accesstoken') || k.includes('account')
                        );
                        for (const k of keys) {
                            try {
                                const v = JSON.parse(localStorage.getItem(k));
                                if (v && typeof v === 'object') {
                                    const token = v.accessToken || v.access_token;
                                    if (token) return token;
                                    const accounts = v.Account || v.accounts;
                                    if (accounts && accounts[0]) {
                                        const id = accounts[0].homeAccountId;
                                        const cacheKey = Object.keys(localStorage)
                                            .find(x => x.includes(id) && x.includes('accesstoken'));
                                        if (cacheKey) {
                                            const cached = JSON.parse(localStorage.getItem(cacheKey));
                                            return cached?.secret || cached?.accessToken;
                                        }
                                    }
                                }
                            } catch (e) {}
                        }
                        return null;
                    }
                    """
                )
                if token_data:
                    captured_token = token_data
                    logger.info("Token extraído do localStorage")
            except Exception as e:
                logger.debug("Falha ao extrair token do localStorage: %s", e)

        if not captured_token:
            # Salvar screenshot para diagnóstico
            debug_dir = os.path.join(os.path.dirname(__file__), "debug")
            os.makedirs(debug_dir, exist_ok=True)
            screenshot_path = os.path.join(debug_dir, "erro_login.png")
            try:
                page.screenshot(path=screenshot_path)
                logger.warning("Screenshot salvo em %s para diagnóstico", screenshot_path)
            except Exception as e:
                logger.debug("Não foi possível salvar screenshot: %s", e)

        logger.debug("Fechando navegador")
        browser.close()

    if not captured_token:
        logger.error("Token não capturado após login")
        raise RuntimeError(
            "Login concluído, mas não foi possível capturar o token. "
            "Verifique se o login foi bem-sucedido."
        )

    logger.info(
        "Login concluído - matricula=%s, sequencial=%s, zona=%s",
        captured_matricula,
        captured_sequencial,
        captured_zona,
    )
    return ScraperResult(
        access_token=captured_token,
        matricula=captured_matricula,
        sequencial_responsavel=captured_sequencial,
        zona_ligacao=captured_zona,
    )


def fetch_debito_totais(
    access_token: str,
    matricula: str,
    sequencial_responsavel: str,
    zona_ligacao: str = "1",
) -> dict:
    """
    Busca totais de débito para uma matrícula.

    Args:
        access_token: Token JWT Bearer
        matricula: Número da matrícula
        sequencial_responsavel: Sequencial do responsável
        zona_ligacao: Zona de ligação (default: 1)

    Returns:
        Resposta JSON da API
    """
    import requests

    logger.info(
        "Buscando débito totais - matricula=%s, sequencial=%s, zona=%s",
        matricula,
        sequencial_responsavel,
        zona_ligacao,
    )
    url = f"{API_BASE}/fatura/debito-totais/matricula"
    params = {
        "matricula": matricula,
        "sequencialResponsavel": sequencial_responsavel,
        "zonaLigacao": zona_ligacao,
    }
    from http_headers import get_human_headers

    headers = get_human_headers(extra={
        "X-TenantID": API_TENANT_ID,
        "Ocp-Apim-Subscription-Key": API_SUBSCRIPTION_KEY,
        "Authorization": f"Bearer {access_token}",
    })

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    logger.debug("API respondeu com status %d", resp.status_code)
    return resp.json()
