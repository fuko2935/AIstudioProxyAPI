"""Simplified Playwright initialisation for the Qwen chat experience."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import Browser as AsyncBrowser, Page as AsyncPage, expect as expect_async

from config import AI_STUDIO_URL_PATTERN
from .operations import save_error_snapshot

logger = logging.getLogger("AIStudioProxyServer")


async def _initialize_page_logic(browser: AsyncBrowser) -> Tuple[Optional[AsyncPage], bool]:
    """Create a new page, navigate to Qwen chat and ensure the input is ready."""

    logger.info("--- Initialising Qwen chat page ---")

    context_options: Dict[str, Any] = {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }

    auth_state = os.environ.get("ACTIVE_AUTH_JSON_PATH")
    if auth_state and os.path.exists(auth_state):
        context_options["storage_state"] = auth_state
        logger.info(f"Using provided storage state: {auth_state}")

    # Apply proxy settings from the server if available.
    import server

    if server.PLAYWRIGHT_PROXY_SETTINGS:
        context_options["proxy"] = server.PLAYWRIGHT_PROXY_SETTINGS
        logger.info(
            f"Playwright proxy configured: {server.PLAYWRIGHT_PROXY_SETTINGS['server']}"
        )

    context = await browser.new_context(**context_options)

    if os.environ.get("ENABLE_SCRIPT_INJECTION", "false").lower() == "true":
        from .script_manager import script_manager

        await script_manager.add_init_scripts(context)

    page = await context.new_page()

    target_url = f"https://{AI_STUDIO_URL_PATTERN.strip('/')}/"
    logger.info(f"Navigating to {target_url}")

    try:
        await page.goto(target_url, wait_until="domcontentloaded")
        await expect_async(page.locator("#chat-input")).to_be_visible(timeout=15000)
        logger.info("Qwen chat page ready.")
        return page, True
    except Exception as exc:
        logger.error(f"Failed to prepare Qwen chat page: {exc}")
        await save_error_snapshot("init_failure")
        try:
            await context.close()
        except Exception:
            pass
        return None, False


async def _close_page_logic():
    """Close the active page if present."""

    import server

    if server.page_instance and not server.page_instance.is_closed():
        try:
            await server.page_instance.close()
        except Exception as exc:
            logger.warning(f"Error closing Qwen page: {exc}")

    server.page_instance = None
    server.is_page_ready = False
    logger.info("Qwen page closed and state reset.")


async def signal_camoufox_shutdown():
    """Compatibility stub for the historical Camoufox integration."""

    logger.info("signal_camoufox_shutdown invoked (no-op for Qwen mode).")


async def enable_temporary_chat_mode(page: AsyncPage):
    """Qwen chat has no temporary mode – this is a no-op."""

    logger.info("Temporary chat mode toggle is not applicable for Qwen – skipping.")

