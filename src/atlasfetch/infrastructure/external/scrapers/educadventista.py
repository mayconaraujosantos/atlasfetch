"""
Scraper para Educação Adventista (7edu) - parcelas escolares.
Login: CPF + data de nascimento (mm/dd/yyyy).
URL: https://7edu-br.educadventista.org/studentportal/externalpayment
"""

import logging
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from atlasfetch.infrastructure.external.scrapers.base import BaseScraper, ScraperResult

load_dotenv()

logger = logging.getLogger(__name__)

LOGIN_URL = "https://7edu-br.educadventista.org/studentportal/externalpayment"

SELECTOR_CPF = "#cpf"
SELECTOR_BIRTH = "#birthDate"
SELECTOR_BIRTH_MOBILE = "#birthDateMobile"
SELECTOR_BTN_LOGIN = "#btn-login"
# Botão "Parcelas" / "Todas as parcelas do aluno" em .student-button.installments-button
SELECTOR_STUDENT_PARCELAS = ".student-button.installments-button"
SELECTOR_LOCATION = "select[name='locationId']"
SELECTOR_INSTALLMENT_ITEMS = ".installment-item-content"
SELECTOR_BTN_PAY = ".btn-pay"
SELECTOR_BTN_TO_PAY = ".btn-to-pay"
SELECTOR_BTN_GENERATE_PIX = ".btn-generate-pix"
SELECTOR_PIX_INPUT = "input.copy-input, .copy-input"

# Meses em português para parse
MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _formatar_data_nascimento(ddmmyyyy: str) -> tuple[str, str]:
    """
    Converte dd/mm/yyyy ou ddmmyyyy para formatos do site.
    Retorna (yyyy-mm-dd para input date, mm/dd/yyyy para input text).
    Ex: 16091993 ou 16/09/1993 -> ("1993-09-16", "09/16/1993")
    """
    s = re.sub(r"\D", "", ddmmyyyy)
    if len(s) != 8:
        return (ddmmyyyy, ddmmyyyy)
    dia, mes, ano = s[0:2], s[2:4], s[4:8]
    return (f"{ano}-{mes}-{dia}", f"{mes}/{dia}/{ano}")


def _normalizar_data_vencimento(d: str) -> str | None:
    """
    Normaliza data de validade para dd/mm/yyyy.
    Aceita: 10/03/2026, 2026/03/10 00:00:00, 2026-03-10, 10032026.
    Para 8 dígitos: ddmmyyyy (10/03/2026) vs yyyymmdd (2026-03-10).
    Heurística: se dia<=31 e mes<=12, assume ddmmyyyy.
    """
    if not d or not isinstance(d, str):
        return None
    s = re.sub(r"\D", "", d.strip())
    if len(s) == 8:  # ddmmyyyy ou yyyymmdd
        dia, mes = int(s[0:2]), int(s[2:4])
        ano = int(s[4:8])
        if ano <= 2000:
            return f"{s[0:2]}/{s[2:4]}/{s[4:8]}"
        # ano > 2000: distinguir ddmmyyyy de yyyymmdd
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            return f"{dia:02d}/{mes:02d}/{ano}"  # ddmmyyyy (ex: 10032026)
        return f"{int(s[6:8]):02d}/{int(s[4:6]):02d}/{s[0:4]}"  # yyyymmdd (ex: 20260310)
    # yyyy/mm/dd ou yyyy-mm-dd
    m = re.search(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", d)
    if m:
        ano, mes, dia = m.group(1), m.group(2), m.group(3)
        return f"{int(dia):02d}/{int(mes):02d}/{ano}"
    # dd/mm/yyyy ou dd-mm-yyyy
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", d)
    if m:
        dia, mes, ano = m.group(1), m.group(2), m.group(3)
        return f"{int(dia):02d}/{int(mes):02d}/{ano}"
    return None


def _parse_referencia_pt(ref: str) -> tuple[int, int] | None:
    """Extrai (ano, mes) de 'março/2026' ou '03/2026'."""
    ref = ref.strip().lower()
    for nome, num in MESES_PT.items():
        if nome in ref:
            m = re.search(r"(\d{4})", ref)
            if m:
                return (int(m.group(1)), num)
    # Formato MM/YYYY
    m = re.match(r"(\d{1,2})[/\-](\d{4})", ref)
    if m:
        mes, ano = int(m.group(1)), int(m.group(2))
        if 1 <= mes <= 12 and ano > 2000:
            return (ano, mes)
    return None


def _extrair_parcelas_da_pagina(page) -> list[dict]:
    """
    Extrai parcelas da página atual.
    Os dados estão em script tags com allItems ou no dataSource do Kendo Grid.
    """
    parcelas: list[dict] = []

    # Aguardar conteúdo de parcelas carregar
    try:
        page.wait_for_selector(
            f"{SELECTOR_INSTALLMENT_ITEMS}, #installments-content, [id^='wrapper_']",
            timeout=10000,
        )
        page.wait_for_timeout(1500)
    except Exception:
        pass

    # Tentar extrair via evaluate - allItems (regex greedy para pegar array completo)
    script = """
    () => {
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {
            const text = s.textContent || '';
            let match = text.match(/let allItems\\s*=\\s*(\\[[\\s\\S]*?\\])\\s*;/);
            if (match) {
                try {
                    const arr = eval(match[1]);
                    if (Array.isArray(arr) && arr.length > 0) return arr;
                } catch (e) {}
            }
            match = text.match(/dataSource:\\s*\\{[^}]*data:\\s*eval\\s*\\(\\s*(\\[[\\s\\S]*?\\])\\s*\\)/);
            if (match) {
                try {
                    const arr = eval(match[1]);
                    if (Array.isArray(arr) && arr.length > 0) return arr;
                } catch (e) {}
            }
        }
        return [];
    }
    """
    try:
        result = page.evaluate(script)
        if result and isinstance(result, list) and len(result) > 0:
            parcelas = result
            logger.info("Extraídas %d parcelas via script (allItems/dataSource)", len(parcelas))
    except Exception as e:
        logger.debug("Erro ao extrair parcelas via script: %s", e)

    # Fallback: extrair do HTML dos .installment-item-content
    if not parcelas:
        items = page.locator(SELECTOR_INSTALLMENT_ITEMS).all()
        for item in items:
            data_id = item.get_attribute("data-id")
            ref_el = item.locator(".reference-info b").first
            valor_el = item.locator(".installment-value").first
            venc_el = item.locator(".form-group label:has-text('Vencimento') + div").first
            try:
                ref = ref_el.inner_text() if ref_el else ""
                valor_text = valor_el.inner_text() if valor_el else "0"
                venc = venc_el.inner_text() if venc_el else ""
                valor = float(re.sub(r"[^\d,]", "", valor_text).replace(",", "."))
                parcelas.append({
                    "Id": data_id,
                    "ReferenceDate": ref,
                    "DueDate": venc,
                    "TotalToPay": valor,
                    "Value": valor,
                    "StatusPayment": 0,
                })
            except Exception as e:
                logger.debug("Erro ao parse item: %s", e)

    return parcelas


WAIT_PIX = 12000  # 12 segundos entre cada etapa do fluxo PIX (modal pode demorar)


def _extrair_pix_do_html(html: str) -> dict:
    """
    Extrai codigoPix e qrcodeBase64 do HTML via regex.
    Fallback quando evaluate/locators falham - busca os padrões no HTML bruto.
    """
    out = {"codigoPix": "", "qrcodeBase64": ""}
    if not html or len(html) < 100:
        return out
    # PIX Copia e Cola: value="00020101..." ou value='00020101...'
    m = re.search(r'value\s*=\s*["\'](00020101[^"\']{50,})["\']', html)
    if m:
        out["codigoPix"] = m.group(1).strip()
    # QR Code: src="data:image/png;base64,..." ou src='data:image...'
    m = re.search(r'src\s*=\s*["\'](data:image/[^"\']{100,})["\']', html)
    if m:
        out["qrcodeBase64"] = m.group(1)
    return out


def _extrair_dados_modal_pix(page_or_frame) -> dict:
    """
    Extrai do modal PIX: valor, aluno, dataValidadePix, codigoPix, qrcodeBase64.
    Aceita page ou frame (para iframes).
    Estrutura esperada (do HTML real):
      .modal-body > .qr_code (h3 validade, spans valor/aluno, img base64) + .clipboard (input.copy-input)
    """
    try:
        result = page_or_frame.evaluate(
            """() => {
                const out = { valor: 0, aluno: '', dataValidadePix: '', codigoPix: '', qrcodeBase64: '' };
                const findModal = (root) => {
                    const visible = root.querySelector('.modal.show .modal-body') || root.querySelector('.modal.in .modal-body');
                    if (visible) return visible;
                    return root.querySelector('.modal-body') || root.querySelector('.modal');
                };
                let modal = findModal(document);
                if (!modal) {
                    const roots = document.querySelectorAll('*');
                    for (const el of roots) {
                        if (el.shadowRoot) {
                            modal = findModal(el.shadowRoot);
                            if (modal) break;
                        }
                    }
                }
                if (!modal) return out;

                const text = modal.innerText || '';

                // Data validade: "Pix valido até : 05/03/2026 às 02:34"
                const mValidade = text.match(/Pix\\s+valido\\s+at[eé]\\s*[:\\s]*([\\d/\\sààs:\\d]+)/i)
                    || text.match(/válido\\s+até\\s*[:\\s]*([\\d/\\-\\s\\d:]+)/i)
                    || text.match(/(\\d{2}\\/\\d{2}\\/\\d{4}[\\s\\d:ààs]*)/);
                if (mValidade) out.dataValidadePix = (mValidade[1] || mValidade[0] || '').trim();

                // Valor: "R$ 1.089,00"
                const mValor = text.match(/R\\$\\s*([\\d.,]+)/);
                if (mValor) {
                    const v = mValor[1].replace(/\\./g, '').replace(',', '.');
                    out.valor = parseFloat(v) || 0;
                }

                // Aluno: após "Aluno(a)" - próximo span
                const spans = modal.querySelectorAll('span');
                for (let i = 0; i < spans.length; i++) {
                    if (/Aluno\\s*\\(a\\)/i.test(spans[i].textContent || '')) {
                        const next = spans[i + 1] || spans[i].nextElementSibling;
                        if (next) {
                            out.aluno = (next.textContent || '').trim();
                            break;
                        }
                    }
                }
                if (!out.aluno) {
                    const parts = text.split(/Aluno\\s*\\(a\\)/i);
                    if (parts[1]) out.aluno = parts[1].trim().split(/\\n/)[0].trim();
                }

                // Código PIX - input.copy-input ou #copy-input (HTML real)
                const input = modal.querySelector('input.copy-input') || modal.querySelector('#copy-input')
                    || modal.querySelector('.copy-input') || document.querySelector('#copy-input');
                if (input) out.codigoPix = (input.value || input.getAttribute('value') || input.textContent || '').trim();

                // QR Code base64 - .modal-body .qr_code img (estrutura real do HTML)
                let img = modal.querySelector('.qr_code img[src^="data:image"]')
                    || modal.querySelector('.qr_code img[alt="QRCode"]')
                    || modal.querySelector('img[src^="data:image"]')
                    || modal.querySelector('img[alt="QRCode"]');
                if (!img) {
                    img = document.querySelector('.modal-body .qr_code img[src^="data:image"]')
                        || document.querySelector('.modal-content .qr_code img')
                        || document.querySelector('img[src^="data:image"]');
                }
                if (img) {
                    const src = img.getAttribute('src') || img.src || '';
                    if (src.startsWith('data:image') && src.length > 100) {
                        out.qrcodeBase64 = src;
                    }
                }
                return out;
            }"""
        )
        data = result or {}
        if data:
            logger.info(
                "Modal PIX extraído: valor=%s, aluno=%s, validade=%s, codigoPix=%s chars, qrcode=%s chars",
                data.get("valor"),
                (data.get("aluno") or "")[:30],
                data.get("dataValidadePix", ""),
                len(data.get("codigoPix", "")),
                len(data.get("qrcodeBase64", "")),
            )
        if not data.get("codigoPix") and (data.get("valor") or data.get("aluno")):
            logger.warning("Modal PIX: extraído valor/aluno mas sem codigoPix - verificar se input.copy-input está visível")
        if not data.get("qrcodeBase64") and data.get("codigoPix"):
            logger.warning("Modal PIX: extraído codigoPix mas sem qrcodeBase64 - verificar se img[src^=data:image] está no .qr_code")
        return data
    except Exception as e:
        logger.warning("Erro ao extrair dados modal PIX: %s", e, exc_info=True)
        return {}


def _obter_pix_parcela(
    page, parcel_id: str, valor: float = 0, aluno: str = ""
) -> dict:
    """
    Clica no fluxo Pagar (10s) -> Ir para pagamento (10s) -> Gerar Pix (10s)
    e extrai: codigoPix, dataValidadePix, valor, aluno.
    """
    out = {
        "codigoPix": "",
        "dataValidadePix": "",
        "valor": valor,
        "aluno": aluno,
        "qrcodeBase64": "",
    }
    target_page = page
    try:
        # Limpar seleção anterior (para múltiplas parcelas)
        try:
            cancel_btn = page.locator(".btn-cancel-pay").first
            if cancel_btn.is_visible(timeout=500):
                cancel_btn.click()
                page.wait_for_timeout(800)
        except Exception:
            pass

        # Clicar em Pagar na parcela (por data-id)
        logger.debug("[PIX] Clicando em Pagar para parcela %s", parcel_id[:8])
        btn_pay = page.locator(
            f".installment-item-content[data-id='{parcel_id}'] {SELECTOR_BTN_PAY}"
        ).first
        if not btn_pay.is_visible(timeout=5000):
            logger.warning("[PIX] Botão Pagar não visível para parcela %s", parcel_id[:8])
            return out
        btn_pay.click()
        page.wait_for_timeout(WAIT_PIX)

        # Clicar em Ir para pagamento
        logger.debug("[PIX] Clicando em Ir para pagamento")
        btn_to_pay = page.locator(SELECTOR_BTN_TO_PAY).first
        if not btn_to_pay.is_visible(timeout=5000):
            logger.warning("[PIX] Botão 'Ir para pagamento' não visível para parcela %s", parcel_id[:8])
            return out
        btn_to_pay.click()
        page.wait_for_timeout(WAIT_PIX)

        # Clicar em Gerar código Pix
        btn_pix = None
        for sel in [
            SELECTOR_BTN_GENERATE_PIX,
            "button:has-text('Gerar código Pix')",
            "button:has-text('Gerar código PIX')",
            "a:has-text('Gerar código Pix')",
            "span:has-text('Gerar código Pix')",
            "[class*='generate-pix'], [class*='generate_pix']",
            "text=Gerar código Pix",
            "text=Gerar código PIX",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible(timeout=2000):
                    btn_pix = loc
                    logger.info("[PIX] Botão encontrado com seletor: %s", sel[:50])
                    break
            except Exception:
                continue
        if not btn_pix:
            logger.warning("[PIX] Botão 'Gerar código Pix' não encontrado - PIX não será extraído")
            return out

        # Clicar e verificar se abre popup/nova aba (o click ocorre dentro do with)
        target_page = page
        try:
            with page.expect_popup(timeout=5000) as popup_info:
                btn_pix.click()
            target_page = popup_info.value
            logger.info("[PIX] Popup/nova aba detectada - extraindo dela")
        except Exception:
            target_page = page
            logger.debug("[PIX] Modal na mesma página (sem popup)")
        target_page.wait_for_timeout(WAIT_PIX)

        # Aguardar modal PIX: .clipboard (PIX copia e cola) e .qr_code (imagem)
        modal_ok = False
        for attempt in range(5):
            try:
                target_page.wait_for_selector(
                    ".clipboard, .qr_code, input.copy-input, #copy-input",
                    timeout=12000,
                    state="attached",
                )
                target_page.wait_for_timeout(5000)  # tempo para img base64 e input value
                try:
                    target_page.wait_for_selector(".qr_code img, img[src^='data:image']", timeout=10000, state="attached")
                except Exception:
                    pass
                modal_ok = True
                logger.debug("[PIX] Modal .clipboard/.qr_code detectado (tentativa %d)", attempt + 1)
                break
            except Exception as e:
                logger.debug("[PIX] Aguardando modal (tentativa %d): %s", attempt + 1, e)
                target_page.wait_for_timeout(3000)
        if not modal_ok:
            logger.warning("[PIX] Modal .clipboard/.qr_code não apareceu")

        # Aguardar conteúdo PIX carregar (input com value e img com src) - até 15s
        _wait_script = """() => {
            const inp = document.querySelector('.clipboard input.copy-input') || document.querySelector('#copy-input') || document.querySelector('input.copy-input');
            const img = document.querySelector('.qr_code img') || document.querySelector('img[src^="data:image"]');
            const hasCode = inp && (inp.value || inp.getAttribute('value') || '').trim().length > 50;
            const hasQr = img && img.src && img.src.startsWith('data:image') && img.src.length > 100;
            return hasCode && hasQr;
        }"""
        for attempt in range(15):
            found = False
            for fr in target_page.frames:
                try:
                    if fr.evaluate(_wait_script):
                        found = True
                        logger.debug("[PIX] Conteúdo PIX carregado após %ds", attempt)
                        break
                except Exception:
                    pass
            if found:
                break
            target_page.wait_for_timeout(1000)

        # 1. PRIMEIRO: evaluate direto (.clipboard .copy-input + .qr_code img) - mais rápido
        _eval_script = """() => {
            const r = { codigoPix: '', qrcodeBase64: '' };
            const inp = document.querySelector('.clipboard input.copy-input') || document.querySelector('#copy-input') || document.querySelector('input.copy-input');
            if (inp && (inp.value || inp.getAttribute('value'))) r.codigoPix = (inp.value || inp.getAttribute('value') || '').trim();
            const img = document.querySelector('.qr_code img') || document.querySelector('img[src^="data:image"]');
            if (img && img.src && img.src.startsWith('data:image')) r.qrcodeBase64 = img.src;
            return r;
        }"""
        for idx, fr in enumerate(target_page.frames):
            try:
                ev = fr.evaluate(_eval_script)
                if ev and (ev.get("codigoPix") or ev.get("qrcodeBase64")):
                    out["codigoPix"] = out.get("codigoPix") or ev.get("codigoPix", "")
                    out["qrcodeBase64"] = out.get("qrcodeBase64") or ev.get("qrcodeBase64", "")
                    if ev.get("codigoPix") or ev.get("qrcodeBase64"):
                        logger.info("[PIX] Evaluate (frame %d): codigo=%d chars, qrcode=%d chars", idx, len(out.get("codigoPix", "")), len(out.get("qrcodeBase64", "")))
                    if out.get("codigoPix") and out.get("qrcodeBase64"):
                        break
            except Exception:
                pass

        # 2. Playwright locators (fallback)
        def _try_extract_from_frame(fr, frame_idx: int = 0):
            found = {}
            try:
                # Input - tentar sem is_visible (elemento pode estar em modal overlay)
                for sel in ["#copy-input", "input.copy-input", ".clipboard input"]:
                    try:
                        inp = fr.locator(sel).first
                        if inp.count() > 0:
                            val = (inp.get_attribute("value") or inp.input_value() or "").strip()
                            if val and len(val) > 50:
                                found["codigoPix"] = val
                                break
                    except Exception:
                        pass
                # Img QR Code
                for sel in ["img[alt='QRCode']", ".qr_code img", "img[src^='data:image']", ".modal-body img"]:
                    try:
                        img_el = fr.locator(sel).first
                        if img_el.count() > 0:
                            src = img_el.get_attribute("src")
                            if src and len(src) > 100 and src.startswith("data:image"):
                                found["qrcodeBase64"] = src
                                break
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("[PIX] Playwright frame %d: %s", frame_idx, e)
            return found

        logger.debug("[PIX] Extraindo de %d frame(s)", len(target_page.frames))
        for idx, fr in enumerate(target_page.frames):
            extracted = _try_extract_from_frame(fr, idx)
            if extracted:
                out.update(extracted)
                if extracted.get("codigoPix"):
                    logger.info("[PIX] Código PIX obtido via Playwright (frame %d)", idx)
                if extracted.get("qrcodeBase64"):
                    logger.info("[PIX] QR Code obtido via Playwright: %d chars (frame %d)", len(extracted["qrcodeBase64"]), idx)
                if out.get("codigoPix") and out.get("qrcodeBase64"):
                    break

        # 3. Evaluate modal completo (valor, aluno, validade)
        def _extract_all_frames():
            data = _extrair_dados_modal_pix(target_page)
            if data.get("codigoPix") or data.get("qrcodeBase64"):
                return data
            for i, frame in enumerate(target_page.frames):
                if frame != target_page.main_frame:
                    try:
                        md = _extrair_dados_modal_pix(frame)
                        if md.get("codigoPix") or md.get("qrcodeBase64"):
                            return md
                    except Exception:
                        pass
            return data

        modal_data = _extract_all_frames()
        if modal_data:
            out["codigoPix"] = out.get("codigoPix") or modal_data.get("codigoPix", "")
            out["dataValidadePix"] = modal_data.get("dataValidadePix", "") or out.get("dataValidadePix", "")
            out["qrcodeBase64"] = out.get("qrcodeBase64") or modal_data.get("qrcodeBase64", "")
            if modal_data.get("valor", 0) > 0:
                out["valor"] = modal_data["valor"]
            if modal_data.get("aluno"):
                out["aluno"] = modal_data["aluno"]
        # Retry se qrcode ainda faltando
        if not out.get("qrcodeBase64") and (out.get("codigoPix") or out.get("valor")):
            for retry in range(3):
                target_page.wait_for_timeout(2000)
                for idx, fr in enumerate(target_page.frames):
                    ex = _try_extract_from_frame(fr, idx)
                    if ex.get("qrcodeBase64"):
                        out["qrcodeBase64"] = ex["qrcodeBase64"]
                        logger.info("[PIX] QR Code obtido no retry %d", retry + 1)
                        break
                if out.get("qrcodeBase64"):
                    break

        # 4. Evaluate fallback: .clipboard .copy-input + .qr_code img
        if not out.get("codigoPix") or not out.get("qrcodeBase64"):
            script = """() => {
                const r = { codigoPix: '', qrcodeBase64: '' };
                const inp = document.querySelector('.clipboard input.copy-input') || document.querySelector('#copy-input') || document.querySelector('input.copy-input');
                if (inp) { const v = (inp.value || inp.getAttribute('value') || '').trim(); if (v.length > 50) r.codigoPix = v; }
                const img = document.querySelector('.qr_code img') || document.querySelector('img[src^="data:image"]');
                if (img && img.src && img.src.startsWith('data:image')) r.qrcodeBase64 = img.src;
                return r;
            }"""
            for idx, fr in enumerate(target_page.frames):
                try:
                    fallback = fr.evaluate(script)
                    if fallback and (fallback.get("codigoPix") or fallback.get("qrcodeBase64")):
                        out["codigoPix"] = out.get("codigoPix") or fallback.get("codigoPix", "")
                        out["qrcodeBase64"] = out.get("qrcodeBase64") or fallback.get("qrcodeBase64", "")
                        logger.info("[PIX] Evaluate fallback (frame %d): codigo=%d qrcode=%d", idx, len(out.get("codigoPix", "")), len(out.get("qrcodeBase64", "")))
                        break
                except Exception:
                    pass

        # 5. Regex no HTML bruto (último recurso - funciona mesmo com DOM complexo)
        if not out.get("codigoPix") or not out.get("qrcodeBase64"):
            try:
                html_main = target_page.content()
                rx = _extrair_pix_do_html(html_main)
                if rx.get("codigoPix") or rx.get("qrcodeBase64"):
                    out["codigoPix"] = out.get("codigoPix") or rx.get("codigoPix", "")
                    out["qrcodeBase64"] = out.get("qrcodeBase64") or rx.get("qrcodeBase64", "")
                    logger.info("[PIX] Regex HTML: codigo=%d qrcode=%d", len(out.get("codigoPix", "")), len(out.get("qrcodeBase64", "")))
                for idx, fr in enumerate(target_page.frames):
                    if fr == target_page.main_frame:
                        continue
                    try:
                        html_fr = fr.evaluate("() => document.documentElement.outerHTML")
                        if html_fr:
                            rx = _extrair_pix_do_html(html_fr)
                            if rx.get("codigoPix") or rx.get("qrcodeBase64"):
                                out["codigoPix"] = out.get("codigoPix") or rx.get("codigoPix", "")
                                out["qrcodeBase64"] = out.get("qrcodeBase64") or rx.get("qrcodeBase64", "")
                                logger.info("[PIX] Regex HTML iframe %d: codigo=%d qrcode=%d", idx, len(out.get("codigoPix", "")), len(out.get("qrcodeBase64", "")))
                                break
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("[PIX] Regex HTML falhou: %s", e)

        # Debug: screenshot + HTML quando PIX não extraído
        if not out.get("codigoPix") or not out.get("qrcodeBase64"):
            try:
                _root = os.path.abspath(os.path.join(os.path.dirname(__file__), *([".."] * 5)))
                debug_dir = os.path.join(_root, "debug", "educadventista")
                os.makedirs(debug_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path_png = os.path.join(debug_dir, f"modal_pix_falha_{ts}.png")
                target_page.screenshot(path=path_png)
                path_html = os.path.join(debug_dir, f"modal_pix_falha_{ts}.html")
                with open(path_html, "w", encoding="utf-8") as f:
                    f.write(target_page.content())
                logger.warning(
                    "[PIX] Extração falhou para parcela %s | codigoPix=%s qrcode=%s | Screenshot: %s | HTML: %s",
                    parcel_id[:8],
                    "ok" if out.get("codigoPix") else "FALTA",
                    "ok" if out.get("qrcodeBase64") else "FALTA",
                    path_png,
                    path_html,
                )
            except Exception:
                pass
        else:
            logger.info("[PIX] Sucesso: codigoPix=%d chars, qrcode=%d chars", len(out.get("codigoPix", "")), len(out.get("qrcodeBase64", "")))
    except Exception as e:
        logger.warning("Erro ao obter PIX para parcela %s: %s", parcel_id, e, exc_info=True)
        return out
    finally:
        # Fechar popup se abriu em nova aba
        try:
            if target_page != page and not target_page.is_closed():
                target_page.close()
        except Exception:
            pass
        # Fechar modal na página principal
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            cancel_btn = page.locator(".btn-cancel-pay").first
            if cancel_btn.is_visible(timeout=800):
                cancel_btn.click()
        except Exception:
            pass
    return out


def login(
    cpf: str | None = None,
    data_nascimento: str | None = None,
    *,
    headless: bool = True,
    timeout_ms: int = 30000,
) -> dict:
    """
    Login no portal Educação Adventista.

    Args:
        cpf: CPF (apenas números ou formatado)
        data_nascimento: dd/mm/yyyy ou ddmmyyyy (ex: 16091993)
        headless: navegador invisível

    Returns:
        dict com status e dados da sessão
    """
    cpf = cpf or os.environ.get("EDUCADVENTISTA_CPF")
    data_nascimento = data_nascimento or os.environ.get("EDUCADVENTISTA_DATA_NASCIMENTO")

    if not cpf or not data_nascimento:
        raise ValueError(
            "Defina EDUCADVENTISTA_CPF e EDUCADVENTISTA_DATA_NASCIMENTO "
            "(dd/mm/yyyy ou ddmmyyyy)"
        )

    cpf_limpo = re.sub(r"\D", "", cpf)
    cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(cpf_limpo) == 11 else cpf
    birth_iso, birth_mmddyyyy = _formatar_data_nascimento(data_nascimento)

    logger.info("Iniciando login Educação Adventista - CPF: %s***", cpf_limpo[:4])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
        )
        page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=timeout_ms)
        except PlaywrightTimeout:
            logger.warning("Timeout ao carregar página")

        page.wait_for_selector(SELECTOR_CPF, timeout=timeout_ms)
        page.fill(SELECTOR_CPF, cpf_formatado)

        # birthDate (type=date usa YYYY-MM-DD) ou birthDateMobile (text usa mm/dd/yyyy)
        birth_input = page.locator(SELECTOR_BIRTH).first
        if birth_input.is_visible():
            page.fill(SELECTOR_BIRTH, birth_iso)
        else:
            page.fill(SELECTOR_BIRTH_MOBILE, birth_mmddyyyy)

        page.click(SELECTOR_BTN_LOGIN)
        page.wait_for_load_state("networkidle", timeout=timeout_ms)

        # Verificar se logou - página com alunos ou parcelas
        if "externalpayment" not in page.url:
            raise RuntimeError("Login falhou - verifique CPF e data de nascimento")

        # Aguardar carregamento (alunos ou parcelas)
        page.wait_for_timeout(3000)

        # Aguardar seção de alunos aparecer (carrossel pode demorar)
        try:
            page.wait_for_selector(".student-content, .item, .installments-button", timeout=15000)
            page.wait_for_timeout(5000)
        except Exception:
            pass

        # Clicar no card do aluno primeiro (pode revelar os botões no carrossel)
        try:
            student_card = page.locator(".student-item, .student-content").first
            if student_card.is_visible(timeout=3000):
                student_card.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        # Clicar em "Parcelas" (Todas as parcelas do aluno)
        # O elemento existe no DOM (hasInstallmentsBtn) mas is_visible() pode falhar (overlay, viewport)
        # Usar clique via JavaScript como estratégia principal
        parcelas_clicado = False

        # 1. Tentar clique via JS (bypassa checagem de visibilidade do Playwright)
        try:
            parcelas_clicado = page.evaluate(
                """() => {
                    const btn = document.querySelector('.installments-button');
                    if (btn) {
                        btn.scrollIntoView({ block: 'center' });
                        btn.click();
                        return true;
                    }
                    return false;
                }"""
            )
            if parcelas_clicado:
                logger.info("Botão Parcelas clicado via JavaScript")
        except Exception as e:
            logger.debug("Clique JS Parcelas falhou: %s", e)

        # 2. Fallback: Playwright locator
        if not parcelas_clicado:
            for sel in [SELECTOR_STUDENT_PARCELAS, ".installments-button"]:
                try:
                    loc = page.locator(sel).first
                    loc.scroll_into_view_if_needed(timeout=3000)
                    loc.click(force=True, timeout=3000)
                    parcelas_clicado = True
                    logger.info("Botão Parcelas clicado via locator: %s", sel)
                    break
                except Exception:
                    continue

        if parcelas_clicado:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            page.wait_for_timeout(10000)  # 10 segundos após Parcelas
        else:
            logger.warning("Botão Parcelas não encontrado na página")
            # Debug: screenshot e info da página
            try:
                # debug/ na raiz do projeto (já no .gitignore)
                _root = os.path.abspath(os.path.join(os.path.dirname(__file__), *([".."] * 5)))
                debug_dir = os.path.join(_root, "debug", "educadventista")
                os.makedirs(debug_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                page.screenshot(path=os.path.join(debug_dir, f"parcelas_nao_encontrado_{ts}.png"))
                info = page.evaluate("""() => ({
                    url: location.href,
                    bodyClasses: document.body?.className || '',
                    hasStudentContent: !!document.querySelector('.student-content'),
                    hasInstallmentsBtn: !!document.querySelector('.installments-button'),
                    hasItem: !!document.querySelector('.item'),
                    textSample: document.body?.innerText?.slice(0, 500) || ''
                })""")
                logger.info("Debug página: %s", info)
            except Exception as e:
                logger.debug("Debug screenshot falhou: %s", e)

        # Selecionar localidade se houver mais de uma
        # Nota: option[value!=''] não é seletor CSS válido; filtrar em Python
        location_select = page.locator(SELECTOR_LOCATION).first
        if location_select.is_visible() and location_select.count() > 0:
            options = page.locator(f"{SELECTOR_LOCATION} option").all()
            options_with_value = [o for o in options if (o.get_attribute("value") or "").strip()]
            if options_with_value:
                first_val = options_with_value[0].get_attribute("value")
                if first_val:
                    location_select.select_option(first_val)
                    page.wait_for_timeout(10000)

        parcelas = _extrair_parcelas_da_pagina(page)

        # Filtrar por data de vencimento (opcional)
        # EDUCADVENTISTA_VENCIMENTO=10/03/2026 ou 10032026 - só processa parcelas com esse vencimento
        venc_alvo = os.environ.get("EDUCADVENTISTA_VENCIMENTO", "").strip()
        if venc_alvo and parcelas:
            venc_norm = _normalizar_data_vencimento(venc_alvo)
            if venc_norm:
                parcelas_filtradas = []
                for p in parcelas:
                    due = p.get("DueDate", "")
                    due_norm = _normalizar_data_vencimento(str(due))
                    if due_norm == venc_norm:
                        parcelas_filtradas.append(p)
                if parcelas_filtradas:
                    parcelas = parcelas_filtradas
                    logger.info("Filtrado por vencimento %s: %d parcela(s)", venc_norm, len(parcelas))
                else:
                    logger.warning(
                        "Nenhuma parcela com vencimento %s (EDUCADVENTISTA_VENCIMENTO=%s). "
                        "Disponíveis: %s",
                        venc_norm,
                        venc_alvo,
                        [_normalizar_data_vencimento(str(p.get("DueDate", ""))) for p in parcelas[:5]],
                    )

        # Buscar PIX para cada parcela (opcional, mais lento)
        if parcelas and os.environ.get("EDUCADVENTISTA_BUSCAR_PIX", "").strip() == "1":
            logger.info("Buscando PIX para %d parcela(s)...", len(parcelas))
            for i, item in enumerate(parcelas):
                pid = item.get("Id")
                if not pid:
                    logger.warning("Parcela %d sem Id, pulando PIX", i + 1)
                    continue
                valor = float(item.get("TotalToPay", item.get("Value", 0)))
                aluno = item.get("BeneficiaryName", "")
                logger.info("Obtendo PIX parcela %s (venc %s)...", pid[:8], item.get("DueDate", "?"))
                try:
                    pix_data = _obter_pix_parcela(page, pid, valor=valor, aluno=aluno)
                except Exception as e:
                    logger.error("Falha ao obter PIX parcela %s: %s", pid[:8], e, exc_info=True)
                    continue
                # Considerar vazio apenas quando não há codigoPix E não há qrcodeBase64
                tem_pix = bool(pix_data and (pix_data.get("codigoPix") or pix_data.get("qrcodeBase64")))
                if not tem_pix:
                    logger.warning("PIX retornou vazio para parcela %s", pid[:8])
                    continue
                if pix_data.get("codigoPix") or pix_data.get("qrcodeBase64"):
                        item["codigoPix"] = pix_data.get("codigoPix", "") or item.get("codigoPix", "")
                        item["dataValidadePix"] = pix_data.get("dataValidadePix", "") or item.get("dataValidadePix", "")
                        item["valor"] = pix_data.get("valor", valor) or valor
                        item["aluno"] = pix_data.get("aluno", aluno) or aluno
                        item["qrcodeBase64"] = pix_data.get("qrcodeBase64", "") or item.get("qrcodeBase64", "")
                        logger.info(
                            "PIX obtido: parcela %s | aluno=%s | valor=%s | válido até=%s | qrcode=%s",
                            pid[:8],
                            item.get("aluno", aluno),
                            item.get("valor", valor),
                            pix_data.get("dataValidadePix", "?"),
                            "sim" if pix_data.get("qrcodeBase64") else "não",
                        )
                else:
                    logger.warning(
                        "PIX não encontrado para parcela %s (modal pode não ter carregado)",
                        pid[:8],
                    )

        browser.close()

    return {
        "status": "ok",
        "parcelas": parcelas,
        "quantidade": len(parcelas),
    }


def sync_and_save_escola() -> dict:
    """
    Faz login, extrai parcelas e salva no banco.
    """
    from atlasfetch.infrastructure.persistence.database import salvar_fatura_escola

    logger.info("Iniciando sync Educação Adventista...")
    try:
        result = login(headless=False)
    except Exception as e:
        logger.error("Falha no login Educação Adventista: %s", e, exc_info=True)
        raise
    parcelas = result.get("parcelas", [])

    total_salvos = 0
    seen = set()

    for item in parcelas:
        ref = item.get("ReferenceDate", "")
        parsed = _parse_referencia_pt(ref)
        if not parsed:
            # Fallback: DueDate "2026/03/10 00:00:00"
            due = item.get("DueDate", "")
            m = re.search(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", str(due))
            if m:
                parsed = (int(m.group(1)), int(m.group(2)))
        if not parsed:
            continue

        ano, mes = parsed
        nome_aluno = (item.get("aluno") or item.get("BeneficiaryName") or "aluno_sem_nome")[:200]
        key = (nome_aluno, ano, mes)
        if key in seen:
            continue
        seen.add(key)

        valor = item.get("valor")
        if valor is None:
            valor = float(item.get("TotalToPay", item.get("Value", 0)))
        data_validade_pix = item.get("dataValidadePix", "")
        codigo_pix = item.get("codigoPix", item.get("codigoPIX", ""))
        qrcode_base64 = item.get("qrcodeBase64") or item.get("qrcode_base64") or ""
        if qrcode_base64:
            logger.info("Salvando qrcode_base64: %d chars para %s/%s", len(qrcode_base64), ano, mes)

        salvar_fatura_escola(
            nome_aluno=nome_aluno,
            ano=ano,
            mes=mes,
            valor=valor if valor else None,
            data_validade_pix=data_validade_pix or None,
            codigo_pix=codigo_pix or None,
            qrcode_base64=qrcode_base64 or None,
        )
        total_salvos += 1

    periodos = list({(a, m) for (_, a, m) in seen})
    logger.info(
        "Sync Educação Adventista concluído: %d salvos, %d parcelas, períodos=%s",
        total_salvos,
        len(parcelas),
        periodos,
    )
    return {
        "salvos": total_salvos,
        "parcelas": len(parcelas),
        "periodos": periodos,
    }


class EducadventistaScraper(BaseScraper):
    """Scraper para Educação Adventista (7edu) - parcelas escolares."""

    @property
    def provider_name(self) -> str:
        return "educadventista"

    def login(
        self,
        documento: str,
        senha: str,
        *,
        headless: bool = True,
        **kwargs,
    ) -> ScraperResult:
        # senha = data de nascimento no formato dd/mm/yyyy
        result = login(cpf=documento, data_nascimento=senha, headless=headless)
        parcelas = result.get("parcelas", [])
        return ScraperResult(
            access_token="session",
            matricula=parcelas[0].get("BeneficiaryName") if parcelas else None,
            extra={"parcelas": parcelas, "quantidade": len(parcelas)},
        )
