"""Planner: translates a natural language instruction into an ordered action plan."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def plan(instruction: str) -> list[dict[str, Any]]:
    """Convert a natural language instruction into an ordered list of action objects.

    Each action conforms to the Action union defined in model.py.
    Placeholder until LLM planner is integrated.
    """
    text = instruction.strip()
    if not text:
        return []

    # TODO: call LLM with action schema and return structured action list
    actions: list[dict[str, Any]] = [{"type": "goto", "url": text}]
    logger.debug("Planned %d action(s) for instruction: %.80s", len(actions), text)
    return actions
