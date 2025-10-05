"""Qwen specific helpers for managing models and UI state."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set

from playwright.async_api import TimeoutError, expect as expect_async

from config import EXCLUDED_MODELS_FILENAME
from .operations import DEFAULT_QWEN_MODELS, save_error_snapshot

logger = logging.getLogger("AIStudioProxyServer")


async def _verify_ui_state_settings(page, req_id: str = "unknown") -> Dict[str, Any]:
    """Qwen chat does not expose advanced toggles to manage via automation."""

    return {
        "exists": False,
        "isAdvancedOpen": None,
        "areToolsOpen": None,
        "needsUpdate": False,
    }


async def _force_ui_state_settings(page, req_id: str = "unknown") -> bool:
    logger.info(f"[{req_id}] Qwen UI has no advanced panel to adjust – skipping.")
    return True


async def _force_ui_state_with_retry(page, req_id: str = "unknown", max_retries: int = 1, retry_delay: float = 0.0) -> bool:
    return await _force_ui_state_settings(page, req_id)


async def _verify_and_apply_ui_state(page, req_id: str = "unknown") -> bool:
    return True


async def load_excluded_models(excluded_models_path: str = EXCLUDED_MODELS_FILENAME) -> Set[str]:
    """Read the excluded models list if the file exists."""

    excluded: Set[str] = set()
    if not excluded_models_path:
        return excluded

    if not os.path.exists(excluded_models_path):
        return excluded

    try:
        with open(excluded_models_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                excluded.add(line)
    except Exception as exc:
        logger.warning(f"Failed to read excluded models file: {exc}")

    return excluded


async def _set_model_from_page_display(page, req_id: str = "unknown") -> Optional[str]:
    """Extract the currently selected model from the dropdown button."""

    try:
        button = page.locator('#model-selector-0-button')
        await expect_async(button).to_be_visible(timeout=5000)
        text = (await button.inner_text()).strip()
        if text:
            logger.info(f"[{req_id}] Current Qwen model inferred from UI: {text}")
            return text.split('\n')[0]
    except Exception as exc:
        logger.warning(f"[{req_id}] Unable to detect current model from UI: {exc}")
    return None


async def refresh_model_catalog(page, req_id: str = "model-refresh") -> List[Dict[str, Any]]:
    """Read the available Qwen models from the dropdown menu."""

    logger.info(f"[{req_id}] Refreshing Qwen model catalogue from UI …")
    dropdown_button = page.locator('#model-selector-0-button')
    models: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    menu_opened = False
    try:
        await expect_async(dropdown_button).to_be_visible(timeout=8000)
        await dropdown_button.click()
        menu_opened = True

        menu_items = page.locator('[aria-label="model-item"]')
        await expect_async(menu_items.first).to_be_visible(timeout=5000)
        item_count = await menu_items.count()

        for index in range(item_count):
            option = menu_items.nth(index)
            try:
                label_raw = await option.inner_text()
            except Exception:
                continue

            if not label_raw:
                continue

            lines = [line.strip() for line in label_raw.split('\n') if line.strip()]
            if not lines:
                continue

            display_name = lines[0]
            description = " ".join(lines[1:]) if len(lines) > 1 else ""

            model_id = await option.get_attribute("data-model-id")
            if model_id:
                model_id = model_id.strip()

            if not model_id:
                normalized = re.sub(r"[^a-z0-9_.-]+", "-", display_name.lower())
                model_id = normalized.strip("-") or display_name.lower().replace(" ", "-")

            if model_id in seen_ids:
                continue

            seen_ids.add(model_id)
            models.append({
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "qwen",
                "display_name": display_name,
                "description": description or None,
            })

    except Exception as exc:
        logger.error(f"[{req_id}] Failed to refresh model catalogue: {exc}")
        await save_error_snapshot(f"model_catalog_refresh_error_{req_id}")
        models = []
    finally:
        if menu_opened:
            try:
                await page.keyboard.press('Escape')
            except Exception:
                pass

    logger.info(f"[{req_id}] Retrieved {len(models)} model option(s) from UI.")
    return models


async def switch_ai_studio_model(page, model_id: str, req_id: str) -> bool:
    """Switch Qwen model through the dropdown menu."""

    logger.info(f"[{req_id}] Attempting to switch to Qwen model '{model_id}' …")
    dropdown_button = page.locator('#model-selector-0-button')
    try:
        await expect_async(dropdown_button).to_be_visible(timeout=8000)
        await dropdown_button.click()
    except Exception as exc:
        logger.error(f"[{req_id}] Unable to open model selector: {exc}")
        await save_error_snapshot(f"model_switch_open_fail_{req_id}")
        return False

    # Normalise requested model for comparison
    target_lower = model_id.lower()

    try:
        menu_items = page.locator('[aria-label="model-item"]')
        await expect_async(menu_items.first).to_be_visible(timeout=5000)
        item_count = await menu_items.count()

        for index in range(item_count):
            candidate = menu_items.nth(index)
            try:
                label = (await candidate.inner_text()).strip()
            except Exception:
                continue

            if not label:
                continue

            normalized_label = label.split('\n')[0].strip().lower()
            if target_lower in normalized_label or normalized_label in target_lower:
                await candidate.click()
                logger.info(f"[{req_id}] Model switched to '{label}'.")
                await expect_async(dropdown_button).to_have_text(
                    re.compile(re.escape(label.split('\n')[0])), timeout=5000
                )
                return True

        logger.warning(f"[{req_id}] Target model '{model_id}' not found in menu options.")
        await page.keyboard.press('Escape')
        return False
    except Exception as exc:
        logger.error(f"[{req_id}] Error while selecting model: {exc}")
        await save_error_snapshot(f"model_switch_error_{req_id}")
        try:
            await page.keyboard.press('Escape')
        except Exception:
            pass
        return False


async def _handle_initial_model_state_and_storage(page) -> None:
    """Qwen login flow simply needs the conversation page to load."""

    try:
        await expect_async(page.locator('#chat-input')).to_be_visible(timeout=15000)
        await _set_model_from_page_display(page, "initial")
        import server
        refreshed_models: List[Dict[str, Any]] = []
        try:
            refreshed_models = await refresh_model_catalog(page, req_id="initial-load")
        except Exception as exc:
            logger.error(f"[initial-load] Exception while fetching model list: {exc}")

        if not refreshed_models:
            refreshed_models = DEFAULT_QWEN_MODELS

        server.global_model_list_raw_json = refreshed_models
        server.parsed_model_list = refreshed_models
        if server.model_list_fetch_event:
            server.model_list_fetch_event.set()
    except TimeoutError:
        logger.error("Initial Qwen chat input did not appear in time.")
        await save_error_snapshot("initial_setup_timeout")
        raise

