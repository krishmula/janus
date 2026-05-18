"""Executor: runs the Markov agent loop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.browser import BrowserManager
from app.llm import get_llm_provider

logger = logging.getLogger(__name__)


async def run(
    goal: str, max_steps: int = 40
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    browser = BrowserManager()
    await browser.start()
    llm = get_llm_provider()

    memory: str = ""
    recent_steps: list[dict] = []
    page_state: dict = {}
    steps: list[dict] = []
    final_result = None
    screenshot: bytes = None

    try:
        for step in range(max_steps):
            llm_output = await llm.decide_next_action(
                goal, memory, recent_steps[-3:], page_state, screenshot
            )

            memory = llm_output["memory"]
            next_goal = llm_output["next_goal"]
            action = llm_output["action"]

            print(f"The LLM Output for the current {step} is: ", llm_output)
            print("--------------------------------------------------------")

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
            if action["type"] in ("goto", "click"):
                await asyncio.sleep(1.0)
            page_state = await browser.get_page_state()
            screenshot = await browser.get_screenshot_bytes()

            recent_steps.append(
                {
                    "step": step,
                    "action_type": action["type"],
                    "action_target": action.get("target")
                    or action.get("url")
                    or action.get("key"),
                    "status": result["status"],
                    "error": result["error"],
                    "next_goal": next_goal,
                }
            )

            steps.append(
                {
                    **result,
                    "evaluation": llm_output["evaluation"],
                    "memory_snapshot": memory,
                    "next_goal": next_goal,
                }
            )

    finally:
        await browser.stop()

    return steps, final_result
