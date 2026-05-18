from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.browser import BrowserManager
from app.llm.base import LLMProvider


class MockBrowser(BrowserManager):
    """In-memory BrowserManager that records actions without a real browser."""

    def __init__(self):
        self.started = False
        self.stopped = False
        self.executed_actions: list[dict[str, Any]] = []
        self._page_state: dict[str, Any] = {
            "url": "https://example.com",
            "title": "Example Domain",
        }

    async def start(self):
        self.started = True

    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        self.executed_actions.append(action)
        action_type = action.get("type")
        result: dict[str, Any] = {
            "action_type": action_type,
            "action_data": action,
            "status": "success",
            "error": None,
            "latency_ms": 10.0,
            "screenshot_path": None,
        }
        if action_type == "screenshot":
            result["screenshot_path"] = (
                f"artifacts/screenshots/{action.get('name', 'step')}.png"
            )
        return result

    async def get_page_state(self) -> dict[str, Any]:
        return dict(self._page_state)

    async def get_screenshot_bytes(self) -> bytes | None:
        return None

    async def stop(self):
        self.stopped = True


def _wrap_action(action: dict[str, Any]) -> dict[str, Any]:
    """Wrap a flat action dict into a minimal AgentOutput dict."""
    return {
        "evaluation": "step executed",
        "memory": "task in progress",
        "next_goal": "continue",
        "action": action,
    }


class MockLLM(LLMProvider):
    """LLMProvider that returns a fixed sequence of AgentOutput dicts.

    Accepts either full AgentOutput dicts or flat action dicts (auto-wrapped).
    """

    def __init__(self, actions: list[dict[str, Any]] | None = None):
        raw = actions or [{"type": "done", "result": "finished"}]
        self.actions = [
            a if "evaluation" in a else _wrap_action(a) for a in raw
        ]
        self.call_count = 0
        self.calls: list[tuple[str, str, list, dict]] = []

    async def decide_next_action(
        self,
        goal: str,
        memory: str,
        recent_steps: list[dict[str, Any]],
        page_state: dict[str, Any],
        screenshot: bytes | None = None,
    ) -> dict[str, Any]:
        self.calls.append((goal, memory, recent_steps, page_state))
        if self.call_count >= len(self.actions):
            return _wrap_action({"type": "done", "result": "no more actions"})
        out = self.actions[self.call_count]
        self.call_count += 1
        return out


@pytest.fixture
def mock_browser() -> MockBrowser:
    return MockBrowser()


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM()


@pytest.fixture
def app_client() -> TestClient:
    from app.main import app

    with TestClient(app) as client:
        yield client
