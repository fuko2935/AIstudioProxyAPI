"""Utility helpers shared by the Qwen automation modules."""

from __future__ import annotations

import os
import re
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import expect as expect_async

from config import RESPONSE_CONTAINER_SELECTOR, RESPONSE_TEXT_SELECTOR

logger = logging.getLogger("AIStudioProxyServer")


DEFAULT_QWEN_MODELS = [
    {
        "id": "qwen3-max",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "qwen",
        "display_name": "Qwen3-Max",
        "description": "The most capable flagship Qwen model.",
    },
    {
        "id": "qwen3-vl-235b",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "qwen",
        "display_name": "Qwen3-VL-235B",
        "description": "Large vision-language model.",
    },
]


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
    """Populate the model list with the predefined Qwen catalogue."""

    import server

    server.global_model_list_raw_json = DEFAULT_QWEN_MODELS
    server.parsed_model_list = DEFAULT_QWEN_MODELS
    if server.model_list_fetch_event:
        server.model_list_fetch_event.set()


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

