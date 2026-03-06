"""
Resolve reCAPTCHA v2 usando IA de visão (OpenAI GPT-4o ou Claude).
Requer OPENAI_API_KEY ou ANTHROPIC_API_KEY no .env.
"""

import base64
import logging
import os
import random
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _ask_openai_vision(image_path: str, prompt: str) -> str:
    """Envia imagem para OpenAI Vision e retorna a resposta."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_VISION_MODEL", "gpt-4o"),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


def _ask_openai_instruction(image_path: str) -> str:
    """Pergunta qual objeto selecionar na instrução do reCAPTCHA."""
    prompt = """This image shows the reCAPTCHA instruction text. 
Return ONLY the object/category to select, in English, one or two words.
Example: "traffic lights", "bicycles", "crosswalks", "buses".
Do not include "Select all" or similar. Just the target object."""
    return _ask_openai_vision(image_path, prompt)


def _ask_openai_tile_contains(image_path: str, object_name: str) -> bool:
    """Pergunta se o tile contém o objeto."""
    prompt = f"""Does this image contain {object_name}? 
Answer with ONLY "true" or "false"."""
    resp = _ask_openai_vision(image_path, prompt).lower()
    return "true" in resp or "yes" in resp


def _solve_image_challenge(bframe, screenshots_dir: Path, max_attempts: int = 5) -> bool:
    """Resolve o desafio de imagens do reCAPTCHA (quando bframe já está visível)."""
    challenge_frame = bframe
    for attempt in range(max_attempts):
        logger.info("Desafio de imagem reCAPTCHA - tentativa %d/%d", attempt + 1, max_attempts)

        instruction_el = challenge_frame.locator(".rc-imageselect-instructions")
        instruction_el.wait_for(state="visible", timeout=5000)
        inst_path = screenshots_dir / f"instruction_{attempt}.png"
        instruction_el.screenshot(path=str(inst_path))
        object_name = _ask_openai_instruction(str(inst_path))
        logger.info("Objeto a selecionar: %s", object_name)

        table = challenge_frame.locator("table.rc-imageselect-table")
        tiles = table.locator("td")
        count = tiles.count()
        tiles_to_click = []
        for i in range(count):
            tile = tiles.nth(i)
            tile_path = screenshots_dir / f"tile_{attempt}_{i}.png"
            tile.screenshot(path=str(tile_path))
            if _ask_openai_tile_contains(str(tile_path), object_name):
                tiles_to_click.append(i)

        logger.info("Tiles a clicar: %s", tiles_to_click)
        for i in tiles_to_click:
            tiles.nth(i).click(force=True)
            time.sleep(random.uniform(0.2, 0.5))

        verify_btn = challenge_frame.locator("#recaptcha-verify-button")
        if verify_btn.is_visible():
            verify_btn.click(force=True)
            time.sleep(2)
            if verify_btn.get_attribute("disabled"):
                logger.info("reCAPTCHA resolvido")
                return True

        time.sleep(1)

    return False


def solve_recaptcha_challenge_if_visible(page, timeout_ms: int = 5000) -> bool:
    """
    Resolve o desafio de imagem do reCAPTCHA apenas se ele já estiver visível.
    Para reCAPTCHA invisível: clique em Entrar primeiro, depois chame esta função.
    Retorna True se não há desafio ou se resolveu; False se falhou.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY não configurado. Defina no .env para resolver reCAPTCHA automaticamente."
        )

    screenshots_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "atlasfetch_recaptcha"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    try:
        bframe = page.frame_locator(
            "iframe[src*='recaptcha'][src*='bframe'], iframe[src*='recaptcha.net'][src*='bframe'], "
            "iframe[title*='challenge' i], iframe[title*='expires' i]"
        ).first
        bframe.locator(".rc-imageselect-table").wait_for(state="visible", timeout=timeout_ms)
        return _solve_image_challenge(bframe, screenshots_dir)
    except Exception:
        logger.info("Nenhum desafio de imagem visível (reCAPTCHA pode ter passado)")
        return True


def solve_recaptcha_v2(page) -> bool:
    """
    Resolve reCAPTCHA v2 na página usando IA de visão.
    Tenta clicar no checkbox; para reCAPTCHA invisível, retorna False (use fluxo alternativo).
    Resolve desafios de imagem quando aparecem.
    Retorna True se passou, False caso contrário.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY não configurado. Defina no .env para resolver reCAPTCHA automaticamente."
        )

    screenshots_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "atlasfetch_recaptcha"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Tentar clicar no checkbox (reCAPTCHA visível)
        # Para invisível (rc-anchor-invisible), o clique pode falhar - use fluxo com Entrar primeiro
        try:
            anchor = page.frame_locator(
                "iframe[src*='recaptcha'][src*='anchor'], iframe[src*='recaptcha.net'][src*='anchor'], "
                "iframe[title*='reCAPTCHA'], iframe[title*='recaptcha']"
            ).first
            checkbox = anchor.locator(".recaptcha-checkbox-border, #recaptcha-anchor, .rc-anchor")
            checkbox.wait_for(state="visible", timeout=5000)
            checkbox.click(force=True)  # force=True evita "intercepts pointer events"
            time.sleep(2)
        except Exception as e:
            logger.info("Checkbox não clicável (provavelmente reCAPTCHA invisível): %s", e)
            return False

        # 2. Verificar se apareceu desafio de imagem (bframe)
        bframe = page.frame_locator(
            "iframe[src*='recaptcha'][src*='bframe'], iframe[src*='recaptcha.net'][src*='bframe'], "
            "iframe[title*='challenge' i], iframe[title*='expires' i]"
        ).first
        try:
            bframe.locator(".rc-imageselect-table").wait_for(state="visible", timeout=3000)
        except Exception:
            logger.info("reCAPTCHA passou sem desafio de imagem")
            return True

        if not _solve_image_challenge(bframe, screenshots_dir):
            logger.warning("Não foi possível resolver reCAPTCHA após tentativas")
            return False
        return True

    except Exception as e:
        logger.exception("Erro ao resolver reCAPTCHA: %s", e)
        return False
