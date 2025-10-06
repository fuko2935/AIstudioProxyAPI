import asyncio
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from browser_utils import model_management as mm


class DummyExpect:
    def __init__(self, target):
        self._target = target

    async def to_be_visible(self, timeout=None):
        if hasattr(self._target, "validate_visible"):
            await self._target.validate_visible()
        return True


def fake_expect(target):
    return DummyExpect(target)


@pytest.fixture(autouse=True)
def patch_expect_and_sleep(monkeypatch):
    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(mm, "expect_async", fake_expect)
    monkeypatch.setattr(mm.asyncio, "sleep", fast_sleep)


class FakeKeyboard:
    def __init__(self):
        self.pressed = []

    async def press(self, key):
        self.pressed.append(key)


class FakeElement:
    def __init__(self, attrs=None, text="", visible=True):
        self.attrs = attrs or {}
        self.text = text
        self.visible = visible
        self.clicked = False

    async def click(self, timeout=None):
        self.clicked = True

    async def get_attribute(self, name):
        return self.attrs.get(name)

    async def inner_text(self):
        return self.text

    async def validate_visible(self):
        if not self.visible:
            raise AssertionError("element not visible")
        return True


class FakeLocator:
    def __init__(self, elements):
        self._elements = elements

    @property
    def first(self):
        return self._elements[0]

    async def count(self):
        return len(self._elements)

    def nth(self, index):
        return self._elements[index]


class FakePage:
    def __init__(self, button, items):
        self._button = button
        self._items = items
        self.keyboard = FakeKeyboard()

    def locator(self, selector):
        if selector == "#model-selector-0-button":
            return self._button
        if selector == '[aria-label="model-item"]':
            return FakeLocator(self._items)
        raise KeyError(selector)

    def is_closed(self):
        return False


class ClosedPage:
    def is_closed(self):
        return True


def test_refresh_model_catalog_parses_unique_models(monkeypatch):
    button = FakeElement()
    items = [
        FakeElement(
            attrs={
                "data-model-id": "openai/gpt-4o-mini",
                "data-owned-by": "openai",
                "data-model-description": "Mini GPT-4o",
            },
            text="GPT-4o mini\nMini GPT-4o",
        ),
        FakeElement(
            attrs={
                "data-model-id": "gpt-4o-mini",
                "data-model-description": "duplicate should be ignored",
            },
            text="GPT-4o mini duplicate\nignored",
        ),
        FakeElement(
            attrs={},
            text="Alpha\nFriendly model",
        ),
    ]

    page = FakePage(button, items)

    monkeypatch.setattr(mm.time, "time", lambda: 1_700_000_000)

    results = asyncio.run(mm.refresh_model_catalog(page, req_id="test-case"))

    assert button.clicked, "refresh should click the selector button"
    assert page.keyboard.pressed == ["Escape"], "menu should be closed with Escape"
    assert [model["id"] for model in results] == ["Alpha", "gpt-4o-mini"]

    first, second = results

    assert first["display_name"] == "Alpha"
    assert first["description"] == "Friendly model"
    assert first["owned_by"] == "ai_studio"
    assert first["created"] == 1_700_000_000

    assert second["display_name"] == "GPT-4o mini"
    assert second["description"] == "Mini GPT-4o"
    assert second["owned_by"] == "openai"
    assert second["created"] == 1_700_000_000


def test_refresh_model_catalog_returns_empty_when_page_closed():
    closed_page = ClosedPage()

    results = asyncio.run(mm.refresh_model_catalog(closed_page, req_id="closed"))

    assert results == []
