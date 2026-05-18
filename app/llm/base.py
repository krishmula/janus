"""LLM provider base interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract interface for LLM calls used by the Janus executor."""

    @abstractmethod
    async def decide_next_action(
        self,
        goal: str,
        memory: str,
        recent_steps: list[dict[str, Any]],
        page_state: dict[str, Any],
        screenshot: bytes | None,
    ) -> dict[str, Any]:
        """Return AgentOutput dict: evaluation, memory, next_goal, action."""
