"""Executor: runs each planned action and collects per-step results."""

from __future__ import annotations

import logging
from typing import Any

from app.planner import plan

logger = logging.getLogger(__name__)


async def execute_action(action: dict[str, Any]) -> dict[str, Any]:
    """Execute a single action object and return a step result.

    Placeholder until Playwright runner is integrated.
    """
    return {
        "action": action,
        "status": "pending",
        "latency_ms": None,
        "screenshot_path": None,
        "error": None,
    }


async def run(instruction: str) -> list[dict[str, Any]]:
    """Plan and execute all actions for an instruction, returning step results."""
    actions = await plan(instruction)
    results: list[dict[str, Any]] = []
    for action in actions:
        step_result = await execute_action(action)
        results.append(step_result)
        if step_result["status"] == "failed":
            logger.warning("Action failed, halting run: %s", action)
            break
    return results
