"""
Scraper para Amazonas Energia (luz).
Login em agencia.amazonasenergia.com com CPF/CNPJ e senha.
API: amenergia.pigz.app (Authorization Basic).
O portal atual usa checkbox "Não sou um robô" no próprio formulário.
"""

import logging
import os
import re
import time
import json
import base64
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from atlasfetch.infrastructure.external.scrapers.base import BaseScraper, ScraperResult

load_dotenv()

logger = logging.getLogger(__name__)

# Fallback .env (opcional) - se não houver token no banco
AUTH_HEADER_ENV = "AMAZONAS_ENERGIA_AUTH_HEADER"
UNIT_ID_ENV = "AMAZONAS_ENERGIA_UNIT_ID"
UNIT_IDS_ENV = "AMAZONAS_ENERGIA_UNIT_IDS"  # Múltiplos: 991643,24988197
CLIENT_ID_ENV = "AMAZONAS_ENERGIA_CLIENT_ID"

# URLs
LOGIN_URL = "https://agencia.amazonasenergia.com/"
API_BASE = "https://amenergia.pigz.app"
API_AGENCIA_BASE = "https://api-agencia.amazonasenergia.com"

# Seletores do formulário (novo portal)
DOCUMENT_SELECTORS = ["#CPF_CNPJ", "input[name='CPF_CNPJ']", "#document", "input[name='document']"]
PASSWORD_SELECTORS = ["#SENHA", "input[name='SENHA']", "#password", "input[name='password']"]
ENTRAR_SELECTORS = [
    "button[type='submit']",
    "button:has-text('Entrar')",
    "button.login_consult_button[type='submit']",
]
SELECTOR_NAO_SOUBO = "#nao-sou-robo, input[id='nao-sou-robo']"


def _decode_bearer_payload(auth_header: str | None) -> dict:
    """Decodifica payload JWT (Bearer) sem validar assinatura."""
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return {}
    token = auth_header.split(" ", 1)[1].strip()
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload_b64 = parts[1]
    payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        obj = json.loads(raw.decode("utf-8", errors="ignore"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _unit_ids_from_bearer(auth_header: str | None) -> list[str]:
    """Extrai UCS do payload Bearer (campo UCS)."""
    payload = _decode_bearer_payload(auth_header)
    ucs = payload.get("UCS")
    if isinstance(ucs, list):
        return [str(u).strip() for u in ucs if str(u).strip()]
    return []


def _extract_auth_from_login_response(data: dict) -> str | None:
    """Extrai token da resposta do /api/autenticacao/login (nomes comuns)."""
    if not isinstance(data, dict):
        return None
    for key in ("accessToken", "access_token", "token", "jwt", "Authorization", "authorization"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            token = val.strip()
            if token.lower().startswith("bearer "):
                return token
            # Se vier só o JWT, normaliza para Bearer
            if token.count(".") >= 2:
                return f"Bearer {token}"
            return token
    return None


def _first_visible(page, selectors: list[str], timeout_ms: int = 2000):
    """Retorna o primeiro locator visível dentre uma lista de seletores."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def _preencher_login(page, documento: str, senha: str) -> bool:
    """Preenche documento e senha no formulário do portal atual/legado."""
    doc_loc = _first_visible(page, DOCUMENT_SELECTORS, timeout_ms=4000)
    pass_loc = _first_visible(page, PASSWORD_SELECTORS, timeout_ms=4000)
    if not doc_loc or not pass_loc:
        return False
    doc_loc.fill(documento)
    pass_loc.fill(senha)
    return True


def _marcar_nao_sou_robo(page) -> None:
    """Marca checkbox customizado 'Não sou um robô' quando presente."""
    try:
        chk = page.locator(SELECTOR_NAO_SOUBO).first
        if chk.count() > 0:
            # Em alguns frontends, set_checked evita problemas de click em overlays.
            chk.set_checked(True, timeout=3000)
            logger.info("Checkbox 'Não sou um robô' marcado")
    except Exception as e:
        logger.debug("Checkbox 'Não sou um robô' não marcado: %s", e)


def _clicar_entrar(page) -> bool:
    """Clica no botão Entrar (novo portal + fallback legado)."""
    btn = _first_visible(page, ENTRAR_SELECTORS, timeout_ms=2500)
    if not btn:
        logger.debug("Botão Entrar não encontrado")
        return False
    try:
        btn.click()
        logger.info("Clicou em Entrar")
        return True
    except Exception as e:
        logger.debug("Falha ao clicar em Entrar: %s", e)
        return False


def login(
    documento: str | None = None,
    senha: str | None = None,
    *,
    headless: bool = False,
    timeout_ms: int = 60000,
    wait_manual_seconds: int = 120,
) -> dict:
    """
    Login no site Amazonas Energia e captura credenciais para a API.

    Preenche CPF e senha, abre navegador. Você resolve o reCAPTCHA.
    O scraper clica em Entrar a cada 8s e captura o token.

    Args:
        documento: CPF ou CNPJ (default: AMAZONAS_ENERGIA_CPF)
        senha: Senha (default: AMAZONAS_ENERGIA_SENHA)
        headless: Se True, esconde o navegador (reCAPTCHA exige visível)

    Returns:
        dict com access_token (Basic base64), unit_id, e demais dados capturados
    """
    documento = documento or os.environ.get("AMAZONAS_ENERGIA_CPF")
    senha = senha or os.environ.get("AMAZONAS_ENERGIA_SENHA")

    if not documento or not senha:
        raise ValueError(
            "Defina AMAZONAS_ENERGIA_CPF e AMAZONAS_ENERGIA_SENHA "
            "(variáveis de ambiente ou parâmetros)"
        )

    logger.info("Iniciando login Amazonas Energia - documento: %s***", documento[:4])

    captured_auth_header: str | None = None
    captured_unit_id: str | None = None
    captured_client_id: str | None = None
    captured_recaptcha_token: str | None = None
    captured_login_response: dict | None = None
    captured_consumes: dict | None = None

    def handle_response(response):
        nonlocal captured_auth_header, captured_unit_id, captured_client_id
        nonlocal captured_recaptcha_token, captured_login_response, captured_consumes
        url = response.url
        if "amenergia.pigz.app" not in url and "/mobile/" not in url:
            # Novo backend da agência
            if "api-agencia.amazonasenergia.com" not in url:
                return

        auth = response.request.headers.get("authorization") or response.request.headers.get(
            "Authorization"
        )
        if auth and auth.strip():
            auth = auth.strip()
            # Preferir Bearer (portal novo). Se só houver Basic, manter como fallback.
            if auth.lower().startswith("bearer "):
                captured_auth_header = auth
            elif not captured_auth_header:
                captured_auth_header = auth

        client_id = response.request.headers.get("x-client-id")
        if client_id:
            captured_client_id = client_id.strip()

        recaptcha_token = response.request.headers.get("x-recaptcha-token")
        if recaptcha_token:
            captured_recaptcha_token = recaptcha_token.strip()
            logger.info(
                "x-recaptcha-token capturado (%d chars)",
                len(captured_recaptcha_token),
            )

        unit_hdr = response.request.headers.get("x-consumer-unit")
        if unit_hdr and not captured_unit_id:
            captured_unit_id = unit_hdr.strip()

        # Capturar retorno explícito do login da agência
        if "/api/autenticacao/login" in url:
            try:
                if response.ok:
                    login_data = response.json()
                    if isinstance(login_data, dict):
                        captured_login_response = login_data
                        logger.info("Resposta de /api/autenticacao/login capturada")
                        login_auth = _extract_auth_from_login_response(login_data)
                        if login_auth:
                            captured_auth_header = login_auth
                            logger.info(
                                "Bearer capturado da resposta de login (%d chars)",
                                len(login_auth),
                            )
            except Exception:
                pass

        # Capturar unit_id da URL /mobile/{id}/consumes
        match = re.search(r"/mobile/(\d+)/consumes", url)
        if match:
            captured_unit_id = match.group(1)
            if response.ok:
                try:
                    captured_consumes = response.json()
                except Exception:
                    pass

    with sync_playwright() as p:
        # Evita popups de permissão (ex.: localização) interrompendo o login.
        browser = p.chromium.launch(
            headless=headless,
            args=["--deny-permission-prompts"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
        )
        page = context.new_page()

        page.on("response", handle_response)

        try:
            logger.info("Acessando %s", LOGIN_URL)
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=timeout_ms)
        except PlaywrightTimeout:
            logger.warning("Timeout ao carregar página")

        # Aguardar formulário de login do novo portal
        logger.info("Aguardando formulário de login...")
        form_ready = False
        for sel in DOCUMENT_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=timeout_ms)
                form_ready = True
                break
            except Exception:
                pass
        if not form_ready or not _preencher_login(page, documento, senha):
            raise RuntimeError("Formulário de login não encontrado no portal da Amazonas Energia")

        # Portal atual: checkbox customizado "Não sou um robô"
        _marcar_nao_sou_robo(page)
        _clicar_entrar(page)

        # Se houver reCAPTCHA (fallback), tenta solver IA se disponível
        solver_available = bool(os.environ.get("OPENAI_API_KEY"))
        if solver_available:
            try:
                from atlasfetch.infrastructure.external.recaptcha_solver import solve_recaptcha_challenge_if_visible
                time.sleep(2)
                solve_recaptcha_challenge_if_visible(page, timeout_ms=8000)
            except Exception as e:
                logger.debug("Solver reCAPTCHA não aplicado: %s", e)

        logger.info("Aguardando captura do token/autorização...")
        for i in range(wait_manual_seconds):
            if captured_auth_header:
                break
            if i % 8 == 0:
                _marcar_nao_sou_robo(page)
                _clicar_entrar(page)
            time.sleep(1)

        # Aguardar captura do token
        for i in range(15):
            if captured_auth_header:
                logger.info("Login capturado após %d segundos", i)
                break
            time.sleep(1)

        browser.close()

    if not captured_auth_header:
        raise RuntimeError(
            "Login concluído, mas cabeçalho Authorization não foi capturado. "
            "Verifique se o checkbox 'Não sou um robô' foi marcado e o login foi aceito."
        )
    auth_header = captured_auth_header
    token_payload = _decode_bearer_payload(auth_header)
    ucs = _unit_ids_from_bearer(auth_header)
    if not captured_unit_id and ucs:
        captured_unit_id = ucs[0]

    result = {
        "access_token": auth_header,
        "unit_id": captured_unit_id,
        "client_id": captured_client_id,
        "recaptcha_token": captured_recaptcha_token,
        "login_response": captured_login_response,
        "ucs": ucs,
        "token_payload": token_payload,
        "consumes": captured_consumes,
        "auth_header": auth_header,
    }
    logger.info(
        "Login finalizado: auth=%s | recaptcha=%s | client_id=%s | unit_id=%s",
        "ok" if auth_header else "faltando",
        "ok" if captured_recaptcha_token else "faltando",
        captured_client_id or "(não capturado)",
        captured_unit_id or "(não capturado)",
    )

    # Salvar no banco para uso em jobs agendados (sem navegador)
    # unit_id pode vir do .env se não foi capturado na URL
    unit_id_para_salvar = captured_unit_id or os.environ.get(UNIT_ID_ENV) or ""
    if auth_header:
        try:
            from atlasfetch.infrastructure.persistence.database import (
                set_amazonas_energia_token,
            )

            set_amazonas_energia_token(auth_header, unit_id_para_salvar)
            logger.info("Token salvo no banco para uso em jobs agendados")
        except Exception as e:
            logger.warning("Não foi possível salvar token no banco: %s", e)

    return result


def get_unit_ids() -> list[str]:
    """
    Retorna lista de unit_ids a sincronizar.
    AMAZONAS_ENERGIA_UNIT_IDS=991643,24988197 ou AMAZONAS_ENERGIA_UNIT_ID=991643
    """
    ids = os.environ.get(UNIT_IDS_ENV, "").strip()
    if ids:
        return [u.strip() for u in ids.split(",") if u.strip()]
    single = os.environ.get(UNIT_ID_ENV, "").strip()
    if single:
        return [single]
    try:
        from atlasfetch.infrastructure.persistence.database import (
            get_amazonas_energia_token,
        )

        _, unit = get_amazonas_energia_token()
        if unit:
            return [unit]
    except Exception:
        pass
    # Fallback: extrair UCS do Bearer salvo no banco/.env
    auth, _ = get_stored_token()
    ids = _unit_ids_from_bearer(auth)
    if ids:
        return ids
    return []


def get_stored_token() -> tuple[str | None, str | None]:
    """
    Retorna (auth_header, unit_id) do banco ou .env.
    unit_id pode vir do .env quando não está no banco.
    """
    try:
        from atlasfetch.infrastructure.persistence.database import (
            get_amazonas_energia_token,
        )

        auth, unit = get_amazonas_energia_token()
        if auth:
            # unit_id do banco ou fallback para .env
            unit = unit or os.environ.get(UNIT_ID_ENV)
            if unit:
                return (auth, unit)
    except Exception as e:
        logger.debug("Token do banco não disponível: %s", e)

    auth = os.environ.get(AUTH_HEADER_ENV)
    unit = os.environ.get(UNIT_ID_ENV)
    if auth and unit:
        return (auth, unit)
    return (None, None)


def get_client_id() -> str | None:
    """Retorna x-client-id para API nova da agência."""
    client_id = (os.environ.get(CLIENT_ID_ENV) or "").strip()
    return client_id or None


def login_and_fetch_faturas_abertas(
    *,
    documento: str | None = None,
    senha: str | None = None,
    unit_id: str | None = None,
    client_id: str | None = None,
    headless: bool = False,
    wait_manual_seconds: int = 120,
) -> dict:
    """
    Faz login no portal, captura Bearer e busca payload de faturas abertas.
    """
    login_result = login(
        documento=documento,
        senha=senha,
        headless=headless,
        wait_manual_seconds=wait_manual_seconds,
    )
    auth_header = login_result.get("auth_header", "")
    if not auth_header.lower().startswith("bearer "):
        raise RuntimeError(
            "O login não capturou Bearer. Sem Bearer não é possível acessar /api/faturas/abertas."
        )

    resolved_client_id = (
        (client_id or "").strip()
        or (login_result.get("client_id") or "").strip()
        or (get_client_id() or "").strip()
    )
    if not resolved_client_id:
        raise RuntimeError("x-client-id ausente. Defina AMAZONAS_ENERGIA_CLIENT_ID no .env.")

    resolved_unit_id = (
        (unit_id or "").strip()
        or (login_result.get("unit_id") or "").strip()
    )
    if not resolved_unit_id:
        ucs = login_result.get("ucs") or _unit_ids_from_bearer(auth_header)
        if ucs:
            resolved_unit_id = str(ucs[0])
    if not resolved_unit_id:
        raise RuntimeError(
            "x-consumer-unit ausente. Informe unit_id ou configure AMAZONAS_ENERGIA_UNIT_ID(S)."
        )

    payload = fetch_faturas_abertas(
        auth_header=auth_header,
        unit_id=resolved_unit_id,
        client_id=resolved_client_id,
    )
    return {
        "auth_header": auth_header,
        "client_id": resolved_client_id,
        "unit_id": resolved_unit_id,
        "payload": payload,
    }


def fetch_consumes_scheduled() -> dict:
    """
    Busca consumos usando token salvo (banco ou .env).
    Para jobs agendados - sem navegador, sem Playwright.
    Levanta erro se token não configurado ou expirado (401).
    """
    auth_header, unit_id = get_stored_token()
    if not auth_header or not unit_id:
        raise RuntimeError(
            "Token Amazonas Energia não configurado. "
            "Rode: python scripts/setup_amazonas_energia_token.py"
        )
    return fetch_consumes(auth_header=auth_header, unit_id=unit_id)


def sync_and_save_luz() -> dict:
    """
    Busca consumos na API e salva no banco.
    Suporta múltiplos unit_ids (AMAZONAS_ENERGIA_UNIT_IDS=991643,24988197).
    """
    import json

    from atlasfetch.domain.value_objects.referencia import parse_referencia
    from atlasfetch.infrastructure.persistence.database import (
        get_amazonas_energia_token,
        salvar_fatura_luz_aberta,
        salvar_fatura_luz,
    )

    auth_header, _ = get_amazonas_energia_token()
    if not auth_header:
        auth_header = os.environ.get(AUTH_HEADER_ENV)
    if not auth_header:
        # Tentar login automático (headless) com checkbox custom do portal atual.
        if os.environ.get("AMAZONAS_ENERGIA_CPF") and os.environ.get("AMAZONAS_ENERGIA_SENHA"):
            logger.info("Token ausente. Tentando login automático no portal atual...")
            try:
                result = login(headless=True, wait_manual_seconds=30)
                auth_header = result["auth_header"]
                logger.info("Login automático concluído. Token salvo no banco.")
            except Exception as e:
                logger.warning("Login automático falhou: %s", e)
                raise RuntimeError(
                    "Token Amazonas Energia não configurado e login automático falhou. "
                    "Rode: make setup-amazonas-energia"
                ) from e
        else:
            raise RuntimeError(
                "Token Amazonas Energia não configurado. "
                "Configure AMAZONAS_ENERGIA_CPF e AMAZONAS_ENERGIA_SENHA "
                "ou rode: make setup-amazonas-energia"
            )

    unit_ids = get_unit_ids()
    client_id = get_client_id()
    if not unit_ids:
        raise RuntimeError(
            "Nenhum unit_id configurado. Defina AMAZONAS_ENERGIA_UNIT_IDS=991643,24988197 "
            "ou AMAZONAS_ENERGIA_UNIT_ID=991643 no .env"
        )

    total_salvos = 0
    resultados: list[dict] = []

    def _extrair_periodos(obj, acc: list) -> None:
        """Extrai registros com referencia (MM/YYYY) ou DT_REF_EDT da API."""
        if isinstance(obj, list):
            for item in obj:
                _extrair_periodos(item, acc)
        elif isinstance(obj, dict):
            ref = (
                obj.get("referencia")
                or obj.get("periodo")
                or obj.get("reference")
                or obj.get("DT_REF_EDT")
                or obj.get("MES_ANO_REFERENCIA")
            )
            parsed = parse_referencia(str(ref)) if ref else None
            if parsed:
                ano, mes = parsed
                acc.append((ano, mes, obj))
            else:
                ano, mes = obj.get("ano"), obj.get("mes")
                if ano and mes:
                    acc.append((int(ano), int(mes), obj))
            for v in obj.values():
                if v is not obj:
                    _extrair_periodos(v, acc)

    for unit_id in unit_ids:
        try:
            # Preferir endpoint novo da agência quando houver Bearer + x-client-id.
            if auth_header.lower().startswith("bearer ") and client_id:
                data = fetch_faturas_abertas(
                    auth_header=auth_header,
                    unit_id=unit_id,
                    client_id=client_id,
                )
            else:
                # Fallback legado (Pigz)
                data = fetch_consumes(auth_header=auth_header, unit_id=unit_id)
        except Exception as e:
            logger.warning("unit_id %s: %s", unit_id, e)
            resultados.append({"unit_id": unit_id, "erro": str(e)})
            continue

        # Novo payload da agência: {"debitos": [...]}
        if isinstance(data, dict) and isinstance(data.get("debitos"), list):
            debitos = [d for d in data.get("debitos", []) if isinstance(d, dict)]
            if not debitos:
                logger.info("unit_id %s sem débitos abertos", unit_id)
                resultados.append(
                    {
                        "unit_id": unit_id,
                        "salvos": 0,
                        "debitos": 0,
                        "periodos": [],
                    }
                )
                continue
            grupos: dict[tuple[int, int], list[dict]] = {}
            for d in debitos:
                # Persistência normalizada (nova tabela)
                try:
                    salvar_fatura_luz_aberta(unit_id, d)
                except Exception as e:
                    logger.debug("Falha ao salvar fatura_luz_aberta (unit=%s): %s", unit_id, e)

                ref = d.get("MES_ANO_REFERENCIA") or d.get("referencia") or d.get("periodo")
                parsed = parse_referencia(str(ref)) if ref else None
                if not parsed:
                    continue
                ano, mes = parsed
                grupos.setdefault((ano, mes), []).append(d)

            if grupos:
                salvos = 0
                for (ano, mes), itens in grupos.items():
                    payload_mes = {"debitos": itens}
                    salvar_fatura_luz(unit_id, ano, mes, json.dumps(payload_mes, ensure_ascii=False))
                    salvos += 1
                total_salvos += salvos
                resultados.append({"unit_id": unit_id, "salvos": salvos, "periodos": list(grupos.keys())})
                continue

        periodos: list[tuple[int, int, dict]] = []
        _extrair_periodos(data, periodos)

        if not periodos:
            from datetime import datetime

            now = datetime.now()
            periodos = [(now.year, now.month, data)]

        seen = set()
        salvos = 0
        for ano, mes, item in periodos:
            if (ano, mes) in seen:
                continue
            seen.add((ano, mes))
            salvar_fatura_luz(unit_id, ano, mes, json.dumps(item, ensure_ascii=False))
            salvos += 1

        total_salvos += salvos
        resultados.append({"unit_id": unit_id, "salvos": salvos, "periodos": list(seen)})

    return {"salvos": total_salvos, "unit_ids": unit_ids, "resultados": resultados}


def fetch_consumes(
    auth_header: str,
    unit_id: str,
) -> dict:
    """
    Busca consumos da unidade consumidora na API Pigz.

    Args:
        auth_header: Valor completo "Basic <base64>"
        unit_id: ID da unidade (ex: 991643)

    Returns:
        Resposta JSON da API /mobile/{unit_id}/consumes

    Raises:
        RuntimeError: Se token expirou (401) - rode setup novamente
    """
    import requests

    url = f"{API_BASE}/mobile/{unit_id}/consumes"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
        "Accept": "application/json, text/plain, */*",
        "Authorization": auth_header,
        "X-Forwarded-Host": "agencia.amazonasenergia.com",
        "Origin": "https://agencia.amazonasenergia.com",
        "Referer": "https://agencia.amazonasenergia.com/",
    }

    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        raise RuntimeError(
            "Token Amazonas Energia expirado. Rode: python scripts/setup_amazonas_energia_token.py"
        )
    resp.raise_for_status()
    return resp.json()


def fetch_faturas_abertas(
    *,
    auth_header: str,
    unit_id: str,
    client_id: str,
) -> dict:
    """
    Busca faturas abertas na API nova da agência.

    Endpoint:
      GET https://api-agencia.amazonasenergia.com/api/faturas/abertas
    """
    import requests

    if not auth_header.lower().startswith("bearer "):
        raise RuntimeError("Para /api/faturas/abertas é necessário Authorization Bearer")
    if not client_id:
        raise RuntimeError(
            "x-client-id não configurado. Defina AMAZONAS_ENERGIA_CLIENT_ID no .env"
        )

    url = f"{API_AGENCIA_BASE}/api/faturas/abertas"
    logger.info(
        "Chamando /api/faturas/abertas com unit_id=%s e client_id=%s",
        unit_id,
        client_id,
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
        "Accept": "application/json, text/plain, */*",
        "Authorization": auth_header,
        "x-client-id": str(client_id),
        "x-consumer-unit": str(unit_id),
        "Origin": "https://agencia.amazonasenergia.com",
        "Referer": "https://agencia.amazonasenergia.com/",
    }

    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        raise RuntimeError(
            "Token Bearer expirado para API da agência. Gere um novo login/token."
        )
    if resp.status_code == 403:
        raise RuntimeError("Acesso negado pela API da agência (verifique x-client-id e unidade).")
    resp.raise_for_status()
    data = resp.json()
    logger.info("Resposta /api/faturas/abertas recebida (status=%d)", resp.status_code)
    # Normalizar para o fluxo existente que espera dict/list.
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"debitos": data}
    return {"raw": data}


class AmazonasEnergiaScraper(BaseScraper):
    """Scraper para Amazonas Energia (luz)."""

    @property
    def provider_name(self) -> str:
        return "amazonas_energia"

    def login(
        self,
        documento: str,
        senha: str,
        *,
        headless: bool = False,
        **kwargs,
    ) -> ScraperResult:
        result = login(
            documento=documento,
            senha=senha,
            headless=headless,
        )
        return ScraperResult(
            access_token=result["auth_header"],
            matricula=result.get("unit_id"),
            extra={
                "unit_id": result.get("unit_id"),
                "consumes": result.get("consumes"),
            },
        )
