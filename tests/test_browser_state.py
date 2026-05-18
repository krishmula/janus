"""Tests for BrowserManager.get_page_state() — Smart DOM extraction."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.browser import BrowserManager, _PAGE_STATE_JS


@pytest.fixture
def browser_with_page():
    """BrowserManager with a mocked page that returns typical Smart DOM data."""
    bm = BrowserManager()
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title = AsyncMock(return_value="Example Domain")
    mock_page.evaluate = AsyncMock(
        return_value={
            "interactive_elements": [
                {"tag": "a", "text": "More information", "role": "link", "selector": None},
                {"tag": "a", "text": "More information...", "role": "link", "selector": None},
            ],
            "headings": [{"tag": "h1", "text": "Example Domain"}],
            "visible_text": "Example Domain. This domain is for use in illustrative examples.",
        }
    )
    bm._page = mock_page
    return bm


class TestEmptyBrowser:
    """get_page_state() when no page is loaded (self._page is None)."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_page_is_none(self):
        bm = BrowserManager()
        result = await bm.get_page_state()
        assert result == {}


class TestPageStateSuccess:
    """Happy-path: page.evaluate() returns valid Smart DOM data."""

    @pytest.mark.asyncio
    async def test_calls_evaluate_with_smart_dom_js(self, browser_with_page):
        await browser_with_page.get_page_state()
        browser_with_page._page.evaluate.assert_called_once_with(_PAGE_STATE_JS)

    @pytest.mark.asyncio
    async def test_returns_url_and_title(self, browser_with_page):
        result = await browser_with_page.get_page_state()
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example Domain"

    @pytest.mark.asyncio
    async def test_returns_interactive_elements(self, browser_with_page):
        result = await browser_with_page.get_page_state()
        elements = result["interactive_elements"]
        assert len(elements) == 2
        assert elements[0]["tag"] == "a"
        assert elements[0]["text"] == "More information"

    @pytest.mark.asyncio
    async def test_returns_headings(self, browser_with_page):
        result = await browser_with_page.get_page_state()
        assert len(result["headings"]) == 1
        assert result["headings"][0] == {"tag": "h1", "text": "Example Domain"}

    @pytest.mark.asyncio
    async def test_returns_visible_text(self, browser_with_page):
        result = await browser_with_page.get_page_state()
        assert "Example Domain" in result["visible_text"]

    @pytest.mark.asyncio
    async def test_has_all_expected_keys(self, browser_with_page):
        result = await browser_with_page.get_page_state()
        assert set(result.keys()) == {
            "url",
            "title",
            "interactive_elements",
            "headings",
            "visible_text",
        }


class TestPageStateFallbacks:
    """Error / edge-case paths for get_page_state()."""

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_evaluate_exception(self, caplog):
        caplog.set_level(logging.WARNING)
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Example Domain")
        mock_page.evaluate = AsyncMock(side_effect=RuntimeError("evaluate failed"))
        bm._page = mock_page

        result = await bm.get_page_state()
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example Domain"
        assert result["interactive_elements"] == []
        assert result["headings"] == []
        assert result["visible_text"] == ""
        assert "Failed to extract smart DOM" in caplog.text

    @pytest.mark.asyncio
    async def test_handles_empty_dom_response(self):
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Example Domain")
        mock_page.evaluate = AsyncMock(return_value={})
        bm._page = mock_page

        result = await bm.get_page_state()
        assert result["interactive_elements"] == []
        assert result["headings"] == []
        assert result["visible_text"] == ""
