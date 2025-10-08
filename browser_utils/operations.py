"""Utility helpers shared by the Qwen automation modules."""

from __future__ import annotations

import asyncio
import os
import re
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import expect as expect_async

from config import (
    RESPONSE_CONTAINER_SELECTOR,
    RESPONSE_TEXT_SELECTOR,
    DEFAULT_QWEN_MODELS as CONFIG_DEFAULT_QWEN_MODELS,
)

logger = logging.getLogger("AIStudioProxyServer")

MODEL_LIST_REFRESH_TTL_SECONDS = int(os.environ.get("MODEL_LIST_REFRESH_TTL_SECONDS", "300"))


def _build_default_models() -> List[Dict[str, Any]]:
    """Produce a timestamped copy of the fallback model catalog."""

    now = int(time.time())
    defaults: List[Dict[str, Any]] = []
    for entry in CONFIG_DEFAULT_QWEN_MODELS:
        enriched = dict(entry)
        created_value = enriched.get("created")
        if not isinstance(created_value, int) or created_value <= 0:
            enriched["created"] = now
        enriched.setdefault("object", "model")
        enriched.setdefault("owned_by", "qwen")
        defaults.append(enriched)
    return defaults


DEFAULT_QWEN_MODELS = _build_default_models()


def get_default_qwen_models() -> List[Dict[str, Any]]:
    """Return a fresh copy of the fallback model definitions."""

    # Regenerate to ensure timestamps remain recent when the fallback path is used repeatedly.
    return _build_default_models()


async def save_error_snapshot(tag: str) -> None:
    """Capture a screenshot and HTML snapshot for debugging."""

    import server

    page = getattr(server, "page_instance", None)
    if not page or page.is_closed():
        logger.warning(f"[{tag}] Unable to capture snapshot – page unavailable.")
        return

    snapshot_dir = Path("logs") / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    screenshot_path = snapshot_dir / f"{tag}_{timestamp}.png"
    html_path = snapshot_dir / f"{tag}_{timestamp}.html"

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception as exc:
        logger.warning(f"[{tag}] Failed to capture screenshot: {exc}")

    try:
        html_content = await page.content()
        html_path.write_text(html_content, encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[{tag}] Failed to save page HTML: {exc}")

    logger.info(f"[{tag}] Snapshot saved to {snapshot_dir}.")


async def _handle_model_list_response(response: Any):
    """Populate the model list cache using the current Qwen UI state."""

    import server

    now = time.time()
    last_refresh = getattr(server, "model_list_last_refreshed", 0.0)
    refresh_in_progress = getattr(server, "model_list_refresh_in_progress", False)
    existing_models = getattr(server, "parsed_model_list", []) or []

    if existing_models and (now - last_refresh) < MODEL_LIST_REFRESH_TTL_SECONDS:
        return existing_models

    if refresh_in_progress:
        return existing_models or get_default_qwen_models()

    models: List[Any] = []
    page = getattr(server, "page_instance", None)

    if page and not page.is_closed():
        try:
            from .model_management import refresh_model_catalog

            setattr(server, "model_list_refresh_in_progress", True)
            models = await refresh_model_catalog(page, req_id="model-response")
            if models:
                server.model_list_last_refreshed = time.time()
        except Exception as exc:
            logger.error(f"[model-response] Failed to collect models from UI: {exc}")
        finally:
            setattr(server, "model_list_refresh_in_progress", False)

    if not models:
        models = existing_models or get_default_qwen_models()

    server.global_model_list_raw_json = models
    server.parsed_model_list = models
    if server.model_list_fetch_event:
        server.model_list_fetch_event.set()

    return models


async def detect_and_extract_page_error(page) -> Optional[str]:
    """Check for a visible error toast on the page."""

    error_locator = page.locator('.chat-toast, .toast-error, .toast-warning')
    if await error_locator.count() == 0:
        return None

    try:
        await expect_async(error_locator.first).to_be_visible(timeout=1000)
        return await error_locator.first.inner_text()
    except Exception:
        return None


async def get_response_via_edit_button(*args, **kwargs):
    raise NotImplementedError("Editing responses is not supported in Qwen mode.")


async def get_response_via_copy_button(*args, **kwargs):
    raise NotImplementedError("Copy helpers are not available in Qwen mode.")


async def _wait_for_response_completion(page, input_locator, submit_button_locator, edit_button_locator, req_id, check_client_disconnected, *_):
    """Approximate completion by waiting for the submit button to re-enable."""

    try:
        await expect_async(submit_button_locator).to_be_enabled(timeout=20000)
        return True
    except Exception:
        return False


async def _get_final_response_content(page, req_id: str, check_client_disconnected) -> str:
    """Fetch the text from the latest assistant response."""

    container_locator = page.locator(RESPONSE_CONTAINER_SELECTOR)
    count = await container_locator.count()
    if count == 0:
        return ""

    response_locator = container_locator.nth(count - 1).locator(RESPONSE_TEXT_SELECTOR).first
    try:
        await expect_async(response_locator).to_have_text(re.compile(r"\S"), timeout=15000)
        return await response_locator.inner_text()
    except Exception:
        return ""


async def get_raw_text_content(response_element, previous_text: str, req_id: str) -> str:
    try:
        text = await response_element.inner_text(timeout=2000)
        return text or previous_text
    except Exception:
        return previous_text


async def force_dismiss_auth_overlays(page, logger=None, req_id: str = "unknown") -> bool:
    """
    Close or remove Qwen authentication prompts that block interactions.

    The Qwen UI frequently changes its guest modal variants. We try a few strategies:
    1. Click known "continue without login" buttons if present.
    2. Remove sign-up/login overlays by inspecting their text content.
    3. Fall back to sending Escape to close any remaining dialogs.

    Returns:
        True if a blocking overlay was dismissed, otherwise False.
    """

    if not page or page.is_closed():
        return False

    button_texts = [
        "Stay logged out",
        "Continue without logging in",
        "Continue as guest",
        "\u7ee7\u7eed\u672a\u767b\u5f55",
        "\u7ee7\u7eed\u4e0d\u767b\u5f55",
        "\u6682\u4e0d\u767b\u5f55",
        "\u5148\u4e0d\u767b\u5f55",
        "Not now",
        "\u7a0d\u540e\u518d\u8bf4",
    ]

    # Try button-based variants first (preferred to DOM removal).
    for text in button_texts:
        locator = page.locator(f"button:has-text('{text}')")
        try:
            await locator.first.wait_for(state="visible", timeout=1200)
            await locator.first.click()
            try:
                await expect_async(locator).to_be_hidden(timeout=1500)
            except Exception:
                pass
            if logger:
                logger.info(f"[{req_id}] Dismissed auth prompt via button '{text}'.")
            await asyncio.sleep(0.1)
            return True
        except Exception:
            continue

    # Some variants use anchor tags instead of buttons.
    for text in button_texts:
        locator = page.locator(f"a:has-text('{text}')")
        try:
            await locator.first.wait_for(state="visible", timeout=1200)
            await locator.first.click()
            if logger:
                logger.info(f"[{req_id}] Dismissed auth prompt via link '{text}'.")
            await asyncio.sleep(0.1)
            return True
        except Exception:
            continue

    # Fallback: look for modern sign-up overlays and remove them directly.
    patterns = [
        "sign up to qwen",
        "log in to qwen",
        "continue with google",
        "continue with github",
        "already have an account",
        "powered by open webui",
        "welcome back to qwen",
        "\u767b\u5f55",
        "\u6ce8\u518c",
    ]

    try:
        removed = await page.evaluate(
            """(patternList) => {
                const lowerPatterns = patternList.map(p => p.toLowerCase());
                let removedAny = false;

                const candidates = Array.from(
                    document.querySelectorAll('div.fixed, div[role="dialog"], div[class*="shadow-qwen"]')
                );

                for (const node of candidates) {
                    if (!node || typeof node.innerText !== 'string') {
                        continue;
                    }
                    const text = node.innerText.toLowerCase();
                    if (!text) {
                        continue;
                    }
                    if (lowerPatterns.some(pattern => text.includes(pattern))) {
                        node.remove();
                        removedAny = true;
                    }
                }

                if (removedAny) {
                    const backdrops = document.querySelectorAll('div.fixed.inset-0');
                    for (const backdrop of backdrops) {
                        const text = (backdrop.innerText || '').trim();
                        if (!text || lowerPatterns.some(pattern => text.includes(pattern))) {
                            backdrop.remove();
                        }
                    }
                    document.body.style.overflow = '';
                }

                return removedAny;
            }""",
            patterns,
        )
        if removed:
            if logger:
                logger.info(f"[{req_id}] Removed blocking auth overlay via DOM cleanup.")
            await asyncio.sleep(0.05)
            return True
    except Exception:
        pass

    # Final attempt: send Escape twice to close any remaining modal.
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.05)
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.05)
    except Exception:
        pass

    return False
