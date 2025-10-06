"""Playwright initialisation for the Qwen chat experience."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import (
    Browser as AsyncBrowser,
    BrowserContext as AsyncBrowserContext,
    Page as AsyncPage,
    TimeoutError as PlaywrightTimeoutError,
    expect as expect_async,
)

from config import (
    AI_STUDIO_URL_PATTERN,
    AUTO_CONFIRM_LOGIN,
    AUTO_SAVE_AUTH,
    AUTH_SAVE_TIMEOUT,
    ENABLE_SCRIPT_INJECTION,
    SAVED_AUTH_DIR,
    USER_INPUT_END_MARKER_SERVER,
    USER_INPUT_START_MARKER_SERVER,
)
from .operations import _handle_model_list_response, save_error_snapshot

logger = logging.getLogger("AIStudioProxyServer")


def _safe_input(prompt: str) -> Optional[str]:
    try:
        return input(prompt)
    except EOFError:
        return None


def _build_target_url() -> str:
    return f"https://{AI_STUDIO_URL_PATTERN.strip('/')}/"


def _target_host() -> str:
    pattern = AI_STUDIO_URL_PATTERN.strip().strip("/")
    if not pattern:
        return ""
    return pattern.split("/")[0]


def _resolve_storage_state_path(launch_mode: str) -> Optional[str]:
    auth_state = os.environ.get("ACTIVE_AUTH_JSON_PATH", "").strip()
    if launch_mode in {"headless", "virtual_headless"}:
        if not auth_state:
            raise RuntimeError("ACTIVE_AUTH_JSON_PATH must be set when running in headless mode.")
        if not os.path.exists(auth_state):
            raise RuntimeError(f"ACTIVE_AUTH_JSON_PATH '{auth_state}' does not exist.")
        return os.path.abspath(auth_state)

    if auth_state:
        if os.path.exists(auth_state):
            return os.path.abspath(auth_state)
        logger.warning("ACTIVE_AUTH_JSON_PATH is set but file is missing: %s", auth_state)

    return None


def _looks_like_login(url: str, target_host: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if target_host and target_host.lower() in lowered:
        return False
    return any(keyword in lowered for keyword in ("login", "signin", "passport", "auth", "account"))


async def _prompt_text(
    loop: asyncio.AbstractEventLoop,
    prompt: str,
    timeout: int,
    default: Optional[str] = None
) -> Optional[str]:
    print(USER_INPUT_START_MARKER_SERVER, flush=True)
    future = loop.run_in_executor(None, _safe_input, prompt)
    try:
        result = await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        logger.info("Input prompt timed out after %s seconds; using default.", timeout)
        result = default
    finally:
        print(USER_INPUT_END_MARKER_SERVER, flush=True)

    if result is None:
        return default
    return result


async def _prompt_yes_no(
    loop: asyncio.AbstractEventLoop,
    prompt: str,
    timeout: int,
    default: bool
) -> bool:
    response = await _prompt_text(loop, prompt, timeout)
    if response is None:
        return default

    parsed = response.strip().lower()
    if not parsed:
        return default
    if parsed in {"y", "yes"}:
        return True
    if parsed in {"n", "no"}:
        return False
    return default


async def _prompt_for_filename(
    loop: asyncio.AbstractEventLoop,
    prompt: str,
    timeout: int,
    default: str
) -> Optional[str]:
    response = await _prompt_text(loop, prompt, timeout, default=default)
    if response is None:
        return default

    parsed = response.strip()
    if not parsed:
        return default
    if parsed.lower() == "cancel":
        return None
    return parsed


async def _save_auth_state(context: AsyncBrowserContext, filename: str) -> None:
    final_name = filename if filename.endswith(".json") else f"{filename}.json"
    target_dir = Path(SAVED_AUTH_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / final_name

    try:
        await context.storage_state(path=str(destination))
    except Exception as exc:
        logger.error("Failed to save authentication state to %s: %s", destination, exc, exc_info=True)
        print(f"   Failed to save authentication state: {exc}", flush=True)
        return

    logger.info("Authentication state saved to %s", destination)
    print(f"   Authentication state saved to: {destination}", flush=True)


async def _maybe_save_auth_state(
    context: AsyncBrowserContext,
    loop: asyncio.AbstractEventLoop,
    launch_mode: str
) -> None:
    save_auth_filename = os.environ.get("SAVE_AUTH_FILENAME", "").strip()
    if save_auth_filename:
        logger.info(
            "Saving authentication state to '%s' as requested by SAVE_AUTH_FILENAME.",
            save_auth_filename
        )
        await _save_auth_state(context, save_auth_filename)
        return

    if AUTO_SAVE_AUTH:
        auto_filename = f"auth_auto_{int(time.time())}.json"
        logger.info("AUTO_SAVE_AUTH enabled; saving authentication state to %s.", auto_filename)
        await _save_auth_state(context, auto_filename)
        return

    if launch_mode != "debug":
        return

    should_save = await _prompt_yes_no(
        loop,
        "   Do you want to save the current browser authentication state? (y/N): ",
        AUTH_SAVE_TIMEOUT,
        default=False
    )
    if not should_save:
        logger.info("Authentication state not saved.")
        return

    default_filename = f"auth_state_{int(time.time())}.json"
    filename = await _prompt_for_filename(
        loop,
        f"   Enter a filename for the auth state (default: {default_filename}, 'cancel' to skip): ",
        AUTH_SAVE_TIMEOUT,
        default_filename
    )
    if not filename:
        logger.info("Authentication state save cancelled.")
        return

    await _save_auth_state(context, filename)


async def _handle_login_flow(
    page: AsyncPage,
    loop: asyncio.AbstractEventLoop,
    target_host: str
) -> None:
    logger.info("Authentication step detected before reaching the Qwen chat interface.")
    if AUTO_CONFIRM_LOGIN:
        logger.info("AUTO_CONFIRM_LOGIN enabled; waiting for the page to redirect automatically.")
    else:
        await _prompt_text(
            loop,
            "   Login detected. Complete authentication in the browser window and press Enter to continue...",
            AUTH_SAVE_TIMEOUT,
            default=""
        )

    try:
        await page.wait_for_url(f"**{target_host}**", timeout=180000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("Timed out while waiting for Qwen chat after authentication.") from exc

    logger.info("Authentication completed; continuing with page initialisation.")


async def _wait_for_chat_ready(
    page: AsyncPage,
    loop: asyncio.AbstractEventLoop,
    target_host: str
) -> None:
    current_url = page.url
    if _looks_like_login(current_url, target_host):
        await _handle_login_flow(page, loop, target_host)

    try:
        await expect_async(page.locator("#chat-input")).to_be_visible(timeout=20000)
    except Exception as exc:
        raise RuntimeError("Qwen chat input did not become visible in time.") from exc


async def _initialize_page_logic(browser: AsyncBrowser) -> Tuple[Optional[AsyncPage], bool]:
    """Create the Qwen chat page and ensure the UI is ready for use."""

    logger.info("Initialising Qwen chat page.")
    launch_mode = os.environ.get("LAUNCH_MODE", "debug").lower()
    logger.info("Detected launch mode: %s", launch_mode)

    loop = asyncio.get_running_loop()

    try:
        storage_state_path = _resolve_storage_state_path(launch_mode)
    except RuntimeError as storage_err:
        logger.error("Storage state configuration error: %s", storage_err)
        await save_error_snapshot("init_storage_state")
        return None, False

    context_options: Dict[str, Any] = {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }
    if storage_state_path:
        context_options["storage_state"] = storage_state_path
        logger.info("Using storage state: %s", storage_state_path)

    target_url = _build_target_url()
    target_host = _target_host()

    context: Optional[AsyncBrowserContext] = None
    page: Optional[AsyncPage] = None

    try:
        import server

        if server.PLAYWRIGHT_PROXY_SETTINGS:
            context_options["proxy"] = server.PLAYWRIGHT_PROXY_SETTINGS
            logger.info(
                "Playwright proxy configured: %s",
                server.PLAYWRIGHT_PROXY_SETTINGS.get("server", "<unknown>")
            )

        context = await browser.new_context(**context_options)

        if ENABLE_SCRIPT_INJECTION:
            from .script_manager import script_manager

            await script_manager.add_init_scripts(context)

        page = await context.new_page()
        page.on("response", _handle_model_list_response)

        logger.info("Navigating to %s", target_url)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

        await _wait_for_chat_ready(page, loop, target_host)

        await _maybe_save_auth_state(context, loop, launch_mode)

        logger.info("Qwen chat page ready.")
        return page, True

    except Exception as exc:
        logger.error("Failed to prepare the Qwen chat page: %s", exc, exc_info=True)
        await save_error_snapshot("init_failure")
        if context:
            try:
                await context.close()
            except Exception:
                pass
        return None, False


async def _close_page_logic():
    """Close the active page and its context if present."""

    import server

    page = getattr(server, "page_instance", None)
    if page and not page.is_closed():
        context = None
        try:
            context = page.context
        except Exception:
            context = None

        try:
            await page.close()
        except Exception as exc:
            logger.warning("Error closing Qwen page: %s", exc)

        if context and not context.is_closed():
            try:
                await context.close()
            except Exception as exc:
                logger.warning("Error closing browser context: %s", exc)

    server.page_instance = None
    server.is_page_ready = False
    logger.info("Qwen page closed and state reset.")


async def signal_camoufox_shutdown():
    """Compatibility stub for the historical Camoufox integration."""

    logger.info("signal_camoufox_shutdown invoked (no-op for Qwen mode).")


async def enable_temporary_chat_mode(page: AsyncPage):
    """Qwen chat does not expose a temporary chat toggle; this is a no-op."""

    logger.info("Temporary chat mode toggle is not available in Qwen chat; skipping.")
