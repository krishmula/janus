"""Executor: runs the Markov agent loop."""

from __future__ import annotations

import logging
from typing import Any

from app.browser import BrowserManager
from app.llm import get_llm_provider

logger = logging.getLogger(__name__)


async def run(
    goal: str, max_steps: int = 10
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    browser = BrowserManager()
    await browser.start()
    llm = get_llm_provider()
    last_action = None
    page_state = {}
    steps: list[dict[str, Any]] = []
    final_result: dict[str, Any] | None = None

    try:
        for step in range(max_steps):
            action = await llm.decide_next_action(goal, last_action, page_state)

            if action["type"] == "done":
                final_page_state = await browser.get_page_state()
                screenshot_result = await browser.execute(
                    {"type": "screenshot", "name": "final"}
                )
                final_result = {
                    "summary": action.get("result"),
                    "url": final_page_state.get("url"),
                    "title": final_page_state.get("title"),
                    "screenshot_path": screenshot_result.get("screenshot_path"),
                }
                break

            result = await browser.execute(action)
            steps.append(result)
            last_action = result
            page_state = await browser.get_page_state()
    finally:
        await browser.stop()

    return steps, final_result
