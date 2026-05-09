from __future__ import annotations

from unittest.mock import patch

import pytest

from app.executor import run
from tests.conftest import MockBrowser, MockLLM


@pytest.fixture
def never_done_llm() -> MockLLM:
    """Always returns goto, never says done."""
    return MockLLM(actions=[
        {"type": "goto", "url": "https://example.com"},
        {"type": "goto", "url": "https://example.com"},
        {"type": "goto", "url": "https://example.com"},
        {"type": "goto", "url": "https://example.com"},
        {"type": "goto", "url": "https://example.com"},
    ])


class TestLoopTermination:
    @pytest.mark.asyncio
    async def test_loop_terminates_at_max_steps(self, never_done_llm):
        browser = MockBrowser()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=never_done_llm),
        ):
            steps, final_result = await run("test", max_steps=3)

        assert len(steps) == 3
        assert final_result is None

    @pytest.mark.asyncio
    async def test_loop_returns_exactly_max_steps(self, never_done_llm):
        browser = MockBrowser()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=never_done_llm),
        ):
            steps, final_result = await run("test", max_steps=5)

        assert len(steps) == 5
        assert final_result is None

    @pytest.mark.asyncio
    async def test_done_action_breaks_loop_immediately(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "finished"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, final_result = await run("test")

        assert len(steps) == 0
        assert final_result is not None
        assert final_result["summary"] == "finished"


class TestBrowserLifecycle:
    @pytest.mark.asyncio
    async def test_browser_is_started(self):
        browser = MockBrowser()
        llm = MockLLM()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert browser.started is True

    @pytest.mark.asyncio
    async def test_browser_is_stopped(self):
        browser = MockBrowser()
        llm = MockLLM()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert browser.stopped is True

    @pytest.mark.asyncio
    async def test_browser_stopped_even_on_error(self, monkeypatch):
        from unittest.mock import AsyncMock

        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "goto", "url": "https://example.com"}])
        monkeypatch.setattr(browser, "get_page_state", AsyncMock(side_effect=RuntimeError("boom")))
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            with pytest.raises(RuntimeError):
                await run("test")

        assert browser.stopped is True


class TestStepRecording:
    @pytest.mark.asyncio
    async def test_steps_have_correct_structure(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, _ = await run("test")

        assert len(steps) == 1
        step = steps[0]
        assert step["action_type"] == "goto"
        assert step["action_data"]["url"] == "https://example.com"
        assert step["status"] == "success"
        assert "latency_ms" in step
        assert "error" in step
        assert "screenshot_path" in step

    @pytest.mark.asyncio
    async def test_steps_exclude_done_action(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, _ = await run("test")

        action_types = [s["action_type"] for s in steps]
        assert "done" not in action_types


class TestFinalResult:
    @pytest.mark.asyncio
    async def test_final_result_populated_on_done(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "task completed"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            _, final_result = await run("test")

        assert final_result is not None
        assert final_result["summary"] == "task completed"

    @pytest.mark.asyncio
    async def test_final_result_has_url_and_title(self):
        browser = MockBrowser()
        browser._page_state = {"url": "https://example.com/story", "title": "The Story"}
        llm = MockLLM(actions=[{"type": "done", "result": "done"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            _, final_result = await run("test")

        assert final_result["url"] == "https://example.com/story"
        assert final_result["title"] == "The Story"

    @pytest.mark.asyncio
    async def test_final_result_has_screenshot_path(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "done"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            _, final_result = await run("test")

        assert final_result["screenshot_path"] == "artifacts/screenshots/final.png"

    @pytest.mark.asyncio
    async def test_final_result_is_none_when_no_done(self, never_done_llm):
        browser = MockBrowser()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=never_done_llm),
        ):
            _, final_result = await run("test", max_steps=3)

        assert final_result is None


class TestMarkovLoop:
    @pytest.mark.asyncio
    async def test_last_action_passed_to_llm(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://a.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert len(llm.calls) == 2
        first_call_last_action = llm.calls[0][1]
        second_call_last_action = llm.calls[1][1]
        assert first_call_last_action is None
        assert second_call_last_action is not None
        assert second_call_last_action["action_type"] == "goto"

    @pytest.mark.asyncio
    async def test_page_state_passed_to_llm(self):
        browser = MockBrowser()
        browser._page_state = {"url": "https://example.com", "title": "Example"}
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://other.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert len(llm.calls) >= 2
        page_state_after_goto = llm.calls[1][2]
        assert page_state_after_goto["url"] == "https://example.com"
        assert page_state_after_goto["title"] == "Example"

    @pytest.mark.asyncio
    async def test_final_screenshot_taken_on_done(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "done"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert len(browser.executed_actions) >= 1
        last_action = browser.executed_actions[-1]
        assert last_action["type"] == "screenshot"
        assert last_action["name"] == "final"
