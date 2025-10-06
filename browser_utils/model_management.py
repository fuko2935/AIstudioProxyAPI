"""Qwen specific helpers for managing models and UI state."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set

from playwright.async_api import Error as PlaywrightAsyncError, TimeoutError, expect as expect_async

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
    """打开模型选择器并解析可用模型列表。"""

    if not page or page.is_closed():
        logger.warning(f"[{req_id}] 页面不可用，无法刷新模型目录。")
        return []

    menu_opened = False
    models: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    created_ts = int(time.time())

    try:
        dropdown_button = page.locator('#model-selector-0-button')
        await expect_async(dropdown_button).to_be_visible(timeout=15000)
        await dropdown_button.click(timeout=5000)
        menu_opened = True
        await asyncio.sleep(0.2)

        menu_items = page.locator('[aria-label="model-item"]')
        await expect_async(menu_items.first).to_be_visible(timeout=15000)
        item_count = await menu_items.count()

        logger.info(f"[{req_id}] 检测到 {item_count} 个模型选项，开始解析。")

        for index in range(item_count):
            option = menu_items.nth(index)

            model_id_value = None
            for attr_name in ("data-model-id", "data-model", "data-value", "data-testid"):
                try:
                    attr_val = await option.get_attribute(attr_name)
                except PlaywrightAsyncError:
                    attr_val = None
                if attr_val:
                    model_id_value = attr_val.strip()
                    if model_id_value:
                        break

            raw_text = ""
            try:
                raw_text = await option.inner_text()
            except PlaywrightAsyncError:
                raw_text = ""

            text_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            display_name = text_lines[0] if text_lines else (model_id_value or "Unknown Model")

            owner_value = None
            for attr_name in ("data-owned-by", "data-owner"):
                try:
                    attr_val = await option.get_attribute(attr_name)
                except PlaywrightAsyncError:
                    attr_val = None
                if attr_val:
                    owner_value = attr_val.strip()
                    if owner_value:
                        break

            description_value = None
            for attr_name in ("data-model-description", "data-description", "data-tooltip", "title", "aria-label"):
                try:
                    attr_val = await option.get_attribute(attr_name)
                except PlaywrightAsyncError:
                    attr_val = None
                if attr_val:
                    description_value = attr_val.strip()
                    if description_value:
                        break

            if not model_id_value and display_name:
                model_id_value = display_name.strip()

            if model_id_value and '/' in model_id_value:
                simple_model_id = model_id_value.split('/')[-1]
            else:
                simple_model_id = model_id_value.strip() if model_id_value else ""

            if not simple_model_id:
                simple_model_id = display_name.replace(" ", "-").lower()

            if simple_model_id in seen_ids:
                continue
            seen_ids.add(simple_model_id)

            if not owner_value:
                owner_value = "ai_studio"

            if not description_value:
                description_value = text_lines[1] if len(text_lines) > 1 else f"Model option for {display_name}"

            models.append({
                "id": simple_model_id,
                "object": "model",
                "created": created_ts,
                "owned_by": owner_value,
                "display_name": display_name,
                "description": description_value,
            })

        models.sort(key=lambda item: item.get("display_name", "").lower())
        logger.info(f"[{req_id}] 模型目录刷新完成，共解析 {len(models)} 个模型。")
        return models

    except PlaywrightAsyncError as playwright_err:
        logger.error(f"[{req_id}] 通过UI刷新模型目录时发生Playwright错误: {playwright_err}")
        await save_error_snapshot(f"model_catalog_refresh_error_{req_id}")
        raise
    except Exception as exc:
        logger.exception(f"[{req_id}] 刷新模型目录时发生未知错误: {exc}")
        await save_error_snapshot(f"model_catalog_refresh_error_{req_id}")
        raise
    finally:
        if menu_opened:
            try:
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.1)
            except Exception as close_err:
                logger.debug(f"[{req_id}] 关闭模型选择器时发生非致命错误: {close_err}")

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

