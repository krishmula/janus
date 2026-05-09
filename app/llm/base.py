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
        last_action: dict[str, Any] | None,
        page_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Given the current page state, return the concrete next action.

        Returns a single raw action dict.  The caller is responsible for
        validation before execution.
        """
