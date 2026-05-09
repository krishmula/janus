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

    async def stop(self):
        self.stopped = True


class MockLLM(LLMProvider):
    """LLMProvider that returns a fixed sequence of actions."""

    def __init__(self, actions: list[dict[str, Any]] | None = None):
        self.actions = actions or [{"type": "done", "result": "finished"}]
        self.call_count = 0
        self.calls: list[tuple[str, dict[str, Any] | None, dict[str, Any]]] = []

    async def decide_next_action(
        self,
        goal: str,
        last_action: dict[str, Any] | None,
        page_state: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((goal, last_action, page_state))
        if self.call_count >= len(self.actions):
            return {"type": "done", "result": "no more actions"}
        action = self.actions[self.call_count]
        self.call_count += 1
        return action


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
