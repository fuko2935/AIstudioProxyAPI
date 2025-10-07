"""Simplified page controller tailored for the Qwen chat experience."""

from __future__ import annotations

import re
from typing import Callable, Optional

from playwright.async_api import expect as expect_async, TimeoutError

from config import (
    PROMPT_TEXTAREA_SELECTOR,
    SUBMIT_BUTTON_SELECTOR,
    RESPONSE_CONTAINER_SELECTOR,
    RESPONSE_TEXT_SELECTOR,
    LOADING_SPINNER_SELECTOR,
    CLEAR_CHAT_BUTTON_SELECTOR,
    CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR,
    CLICK_TIMEOUT_MS,
    WAIT_FOR_ELEMENT_TIMEOUT_MS,
)
from models import ClientDisconnectedError
from .operations import save_error_snapshot


class PageController:
    """Minimal controller that performs Qwen specific interactions."""

    def __init__(self, page, logger, req_id: str):
        self.page = page
        self.logger = logger
        self.req_id = req_id
        self._response_count_before_submit: Optional[int] = None

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _check_disconnect(self, check_client_disconnected: Callable, stage: str) -> None:
        if check_client_disconnected(stage):
            raise ClientDisconnectedError(
                f"[{self.req_id}] Client disconnected at stage: {stage}"
            )

    async def _dismiss_auth_suggestions(self) -> None:
        """Close login prompts or full-screen modals that block interactions."""

        button_texts = [
            "Stay logged out",
            "Continue without logging in",
            "Continue as guest",
            "继续未登录",
            "继续不登录",
            "暂不登录",
            "先不登录",
        ]

        for text in button_texts:
            locator = self.page.locator(f"button:has-text('{text}')")
            try:
                await locator.first.wait_for(state="visible", timeout=1200)
                await locator.first.click()
                await expect_async(locator).to_be_hidden(timeout=1500)
                self.logger.info(f"[{self.req_id}] Dismissed auth prompt via button '{text}'.")
                return
            except Exception:
                continue

        # Some variants render as generic modal overlays without the known button texts.
        modal_root = self.page.locator("div.modal")
        try:
            if await modal_root.first.is_visible(timeout=500):
                modal_buttons = modal_root.locator("button, a")
                for index in range(await modal_buttons.count()):
                    candidate = modal_buttons.nth(index)
                    try:
                        text = (await candidate.inner_text()).strip()
                    except Exception:
                        text = ""
                    try:
                        await candidate.click()
                        await modal_root.first.wait_for(state="hidden", timeout=1500)
                        self.logger.info(f"[{self.req_id}] Dismissed modal overlay via '{text or '<unnamed>'}'.")
                        return
                    except Exception:
                        continue
        except Exception:
            pass

        # Fallback: try sending Escape to close any remaining overlay.
        try:
            await self.page.keyboard.press("Escape")
        except Exception:
            pass

    async def adjust_parameters(
        self,
        request_params: dict,
        page_params_cache: dict,
        params_cache_lock,
        model_id_to_use: str,
        parsed_model_list,
        check_client_disconnected: Callable,
    ) -> None:
        """Qwen web does not expose tunable parameters in the UI."""

        self.logger.info(
            f"[{self.req_id}] Qwen web UI does not expose tunable parameters – skipping."
            )

    # ------------------------------------------------------------------
    async def clear_chat_history(self, check_client_disconnected: Callable) -> None:
        """Trigger the built-in new chat button."""

        self.logger.info(f"[{self.req_id}] Triggering new chat action...")
        self._check_disconnect(check_client_disconnected, "before-clear")

        if not CLEAR_CHAT_BUTTON_SELECTOR:
            self.logger.info(
                f"[{self.req_id}] No clear chat selector configured – skipping."
            )
            return

        button_locator = self.page.locator(CLEAR_CHAT_BUTTON_SELECTOR)
        try:
            await expect_async(button_locator).to_be_visible(timeout=WAIT_FOR_ELEMENT_TIMEOUT_MS)
            await self._dismiss_auth_suggestions()
            await button_locator.click(timeout=CLICK_TIMEOUT_MS)
            self.logger.info(f"[{self.req_id}] New chat button clicked.")
        except Exception as exc:
            self.logger.warning(
                f"[{self.req_id}] Unable to activate new chat button: {exc}"
            )
            await save_error_snapshot(f"clear_chat_{self.req_id}")
            return

        if CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR and CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR != "[data-qwen-not-supported]":
            confirm_locator = self.page.locator(CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR)
            try:
                await expect_async(confirm_locator).to_be_visible(timeout=2000)
                await confirm_locator.click(timeout=CLICK_TIMEOUT_MS)
            except TimeoutError:
                pass
            except Exception as exc:
                self.logger.warning(
                    f"[{self.req_id}] Failed to confirm chat clearing: {exc}"
                )

    # ------------------------------------------------------------------
    async def submit_prompt(
        self, prompt: str, image_list, check_client_disconnected: Callable
    ) -> None:
        """Fill the Qwen textarea and submit the prompt."""

        self.logger.info(f"[{self.req_id}] Preparing to submit prompt…")
        self._check_disconnect(check_client_disconnected, "before-submit")

        textarea = self.page.locator(PROMPT_TEXTAREA_SELECTOR)
        await expect_async(textarea).to_be_visible(timeout=WAIT_FOR_ELEMENT_TIMEOUT_MS)
        try:
            html_preview = await textarea.evaluate("el.outerHTML")
            self.logger.debug(f"[{self.req_id}] Textarea HTML: {html_preview[:120]!r}")
        except Exception:
            pass
        await self._dismiss_auth_suggestions()
        await textarea.click()
        await textarea.fill(prompt)
        await self._dismiss_auth_suggestions()
        try:
            current_value = await textarea.input_value()
            self.logger.debug(f"[{self.req_id}] Textarea current value preview: {current_value[:60]!r}")
        except Exception:
            current_value = None

        response_locator = self.page.locator(RESPONSE_CONTAINER_SELECTOR)
        try:
            self._response_count_before_submit = await response_locator.count()
        except Exception:
            self._response_count_before_submit = None

        submit_locator = self.page.locator(SUBMIT_BUTTON_SELECTOR)
        try:
            await expect_async(submit_locator).to_be_visible(timeout=3000)
            await submit_locator.click(timeout=CLICK_TIMEOUT_MS)
            self.logger.info(f"[{self.req_id}] Prompt submitted via button click.")
        except Exception as click_err:
            self.logger.warning(
                f"[{self.req_id}] Submit button interaction failed ({click_err}); sending Enter key as fallback."
            )
            await save_error_snapshot(f"submit_click_blocked_{self.req_id}")
            await self._dismiss_auth_suggestions()
            await textarea.press("Enter")

        self._check_disconnect(check_client_disconnected, "after-submit")

    # ------------------------------------------------------------------
    async def get_response(self, check_client_disconnected: Callable) -> str:
        """Wait for the assistant response rendered on the page."""

        self.logger.info(f"[{self.req_id}] Waiting for Qwen response…")
        self._check_disconnect(check_client_disconnected, "before-response")

        response_locator = self.page.locator(RESPONSE_CONTAINER_SELECTOR)
        expected_index = self._response_count_before_submit or 0

        try:
            await expect_async(response_locator.nth(expected_index)).to_be_attached(
                timeout=120000
            )
        except TimeoutError:
            self.logger.error(f"[{self.req_id}] Response container did not appear in time.")
            await save_error_snapshot(f"response_timeout_{self.req_id}")
            return ""

        container = response_locator.nth(expected_index)
        text_locator = container.locator(RESPONSE_TEXT_SELECTOR).first

        # Wait for streaming to finish by monitoring the send button and the spinner.
        submit_locator = self.page.locator(SUBMIT_BUTTON_SELECTOR)
        spinner_locator = self.page.locator(LOADING_SPINNER_SELECTOR)

        try:
            await expect_async(text_locator).to_have_text(
                re.compile(r"\S"), timeout=120000
            )
        except TimeoutError:
            self.logger.warning(f"[{self.req_id}] Response text did not populate – continuing anyway.")

        # Wait for loading spinner to disappear if one exists.
        try:
            await expect_async(spinner_locator).to_be_hidden(timeout=10000)
        except TimeoutError:
            pass
        except Exception:
            pass

        # Close post-response login prompts if they appear (e.g. "Stay logged out").
        await self._dismiss_auth_suggestions()

        # Wait for submit button to re-enable as a proxy that streaming finished.
        try:
            await expect_async(submit_locator).to_be_enabled(timeout=15000)
        except Exception:
            pass

        try:
            content = await text_locator.inner_text()
        except Exception as extract_err:
            self.logger.error(f"[{self.req_id}] Failed to read response text: {extract_err}")
            await save_error_snapshot(f"response_extract_error_{self.req_id}")
            content = ""

        self.logger.info(
            f"[{self.req_id}] Retrieved response with {len(content.strip())} characters."
        )
        return content
