from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.executor import run
from app import trace
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
            run_id, steps, final_result = await run("test", max_steps=3)

        assert len(steps) == 3
        assert final_result is None

    @pytest.mark.asyncio
    async def test_loop_returns_exactly_max_steps(self, never_done_llm):
        browser = MockBrowser()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=never_done_llm),
        ):
            run_id, steps, final_result = await run("test", max_steps=5)

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
            run_id, steps, final_result = await run("test")

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
            run_id, steps, _ = await run("test")

        assert len(steps) == 1
        step = steps[0]
        assert step["action_type"] == "goto"
        assert step["action_data"]["url"] == "https://example.com"
        assert step["status"] == "success"
        assert "latency_ms" in step
        assert "error" in step
        assert "screenshot_path" in step
        assert "evaluation" in step
        assert "memory_snapshot" in step
        assert "next_goal" in step

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
            run_id, steps, _ = await run("test")

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
            run_id, _, final_result = await run("test")

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
            run_id, _, final_result = await run("test")

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
            run_id, _, final_result = await run("test")

        assert final_result["screenshot_path"] == "artifacts/screenshots/final.png"

    @pytest.mark.asyncio
    async def test_final_result_is_none_when_no_done(self, never_done_llm):
        browser = MockBrowser()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=never_done_llm),
        ):
            run_id, _, final_result = await run("test", max_steps=3)

        assert final_result is None


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_memory_starts_empty_at_first_call(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "done"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert llm.calls[0][1] == ""

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
        page_state_after_goto = llm.calls[1][3]
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


class TestMemoryManagement:
    @pytest.mark.asyncio
    async def test_memory_from_llm_reaches_next_call(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {
                "evaluation": "navigated",
                "memory": "landed on example.com",
                "next_goal": "find the link",
                "action": {"type": "goto", "url": "https://example.com"},
            },
            {
                "evaluation": "done",
                "memory": "task complete",
                "next_goal": "finish",
                "action": {"type": "done", "result": "finished"},
            },
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        assert llm.calls[1][1] == "landed on example.com"

    @pytest.mark.asyncio
    async def test_recent_steps_passed_to_llm(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        second_call_recent_steps = llm.calls[1][2]
        assert len(second_call_recent_steps) == 1

    @pytest.mark.asyncio
    async def test_recent_steps_capped_at_3(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "goto", "url": "https://example.com"},
            {"type": "goto", "url": "https://example.com"},
            {"type": "goto", "url": "https://example.com"},
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "finished"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test", max_steps=10)

        assert len(llm.calls) == 6
        sixth_call_recent_steps = llm.calls[5][2]
        assert len(sixth_call_recent_steps) == 3

    @pytest.mark.asyncio
    async def test_recent_step_entry_fields(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        entry = llm.calls[1][2][0]
        assert "step" in entry
        assert "action_type" in entry
        assert "action_target" in entry
        assert "status" in entry
        assert "error" in entry
        assert "next_goal" in entry

    @pytest.mark.asyncio
    async def test_recent_steps_action_target_from_url(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        entry = llm.calls[1][2][0]
        assert entry["action_target"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_recent_steps_action_target_from_target(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "click", "target": ".btn"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("test")

        entry = llm.calls[1][2][0]
        assert entry["action_target"] == ".btn"


class TestTraceIntegration:
    @pytest.mark.asyncio
    async def test_run_stored_in_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        trace.init_db(db_path)
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "finished"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            run_id, steps, final_result = await run("find the top post")

        stored = trace.get_run(run_id)
        assert stored is not None
        assert stored["goal"] == "find the top post"
        assert stored["status"] == "completed"

    @pytest.mark.asyncio
    async def test_steps_stored_in_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        trace.init_db(db_path)
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "done", "result": "done"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            run_id, steps, _ = await run("test")

        stored_steps = trace.get_steps(run_id)
        assert len(stored_steps) == 1
        assert stored_steps[0]["action_type"] == "goto"
        assert stored_steps[0]["action_target"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_max_steps_status_stored(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        trace.init_db(db_path)
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "goto", "url": "https://example.com"},
            {"type": "goto", "url": "https://example.com"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            run_id, _, _ = await run("test", max_steps=3)

        stored = trace.get_run(run_id)
        assert stored["status"] == "max_steps"

    @pytest.mark.asyncio
    async def test_final_result_stored_on_done(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        trace.init_db(db_path)
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "all done"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            run_id, _, final_result = await run("test")

        stored = trace.get_run(run_id)
        assert stored["final_result"] is not None
        assert stored["final_screenshot_path"] is not None

    @pytest.mark.asyncio
    async def test_run_id_returned_from_run(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        trace.init_db(db_path)
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "done"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            result = await run("test")

        assert len(result) == 3
        run_id = result[0]
        assert isinstance(run_id, str)
        assert len(run_id) > 0
