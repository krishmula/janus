from __future__ import annotations

from unittest.mock import patch

import pytest

from app.executor import run
from tests.conftest import MockBrowser, MockLLM


class TestGotoClickDone:
    @pytest.mark.asyncio
    async def test_goto_click_done_sequence(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://news.ycombinator.com/"},
            {"type": "click", "target": ".titleline > a"},
            {"type": "done", "result": "navigated to top post"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, final_result = await run("get the top post on hackernews")

        assert len(steps) == 2
        assert steps[0]["action_type"] == "goto"
        assert steps[1]["action_type"] == "click"
        assert final_result["summary"] == "navigated to top post"


class TestDoneOnly:
    @pytest.mark.asyncio
    async def test_done_only_returns_no_steps(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[{"type": "done", "result": "nothing to do"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, final_result = await run("do nothing")

        assert len(steps) == 0
        assert final_result["summary"] == "nothing to do"
        assert len(browser.executed_actions) >= 1
        assert browser.executed_actions[-1]["type"] == "screenshot"


class TestNeverDone:
    @pytest.mark.asyncio
    async def test_exhausts_max_steps(self):
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
            steps, final_result = await run("test", max_steps=2)

        assert len(steps) == 2
        assert final_result is None


class TestGoalPreservation:
    @pytest.mark.asyncio
    async def test_goal_passed_to_llm(self):
        browser = MockBrowser()
        llm = MockLLM()
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            await run("my goal is to search", max_steps=1)

        assert len(llm.calls) >= 1
        goal = llm.calls[0][0]
        assert goal == "my goal is to search"


class TestScreenshotOnDone:
    @pytest.mark.asyncio
    async def test_screenshot_taken_after_actions(self):
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

        executed_types = [a["type"] for a in browser.executed_actions]
        assert executed_types == ["goto", "screenshot"]

    @pytest.mark.asyncio
    async def test_final_result_reflects_page_state(self):
        browser = MockBrowser()
        browser._page_state = {"url": "https://x.com/post/123", "title": "X Post"}
        llm = MockLLM(actions=[{"type": "done", "result": "got the post"}])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            _, final_result = await run("test")

        assert final_result["url"] == "https://x.com/post/123"
        assert final_result["title"] == "X Post"


class TestMultiStepSequence:
    @pytest.mark.asyncio
    async def test_runs_all_steps_then_done(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {"type": "goto", "url": "https://example.com"},
            {"type": "type", "target": "input", "text": "search term"},
            {"type": "press", "key": "Enter"},
            {"type": "click", "target": ".result"},
            {"type": "done", "result": "found results"},
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, final_result = await run("test")

        assert len(steps) == 4
        assert [s["action_type"] for s in steps] == ["goto", "type", "press", "click"]
        assert final_result["summary"] == "found results"


class TestMemoryEvolution:
    @pytest.mark.asyncio
    async def test_memory_evolves_across_steps(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {
                "evaluation": "navigated to HN",
                "memory": "visited HN homepage",
                "next_goal": "click the top post",
                "action": {"type": "goto", "url": "https://news.ycombinator.com/"},
            },
            {
                "evaluation": "clicked successfully",
                "memory": "visited HN, clicked top post",
                "next_goal": "read the article",
                "action": {"type": "done", "result": "navigated to top post"},
            },
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, _ = await run("get the top post on hackernews")

        assert llm.calls[1][1] == "visited HN homepage"
        assert steps[0]["memory_snapshot"] == "visited HN homepage"

    @pytest.mark.asyncio
    async def test_evaluation_stored_in_step_record(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {
                "evaluation": "page loaded successfully",
                "memory": "on example.com",
                "next_goal": "find next target",
                "action": {"type": "goto", "url": "https://example.com"},
            },
            {
                "evaluation": "all done",
                "memory": "task complete",
                "next_goal": "finish",
                "action": {"type": "done", "result": "finished"},
            },
        ])
        with (
            patch("app.executor.BrowserManager", return_value=browser),
            patch("app.executor.get_llm_provider", return_value=llm),
        ):
            steps, _ = await run("test")

        assert steps[0]["evaluation"] == "page loaded successfully"

    @pytest.mark.asyncio
    async def test_next_goal_stored_in_step_record(self):
        browser = MockBrowser()
        llm = MockLLM(actions=[
            {
                "evaluation": "navigated",
                "memory": "on example.com",
                "next_goal": "click the main link",
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
            steps, _ = await run("test")

        assert steps[0]["next_goal"] == "click the main link"
