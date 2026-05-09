"""LLMProvider abstraction for Janus.

All providers return raw dicts so the executor can run its own deterministic
validation / repair loop before turning outputs into Pydantic Action models.

Usage::

    from app.llm import get_llm_provider
    llm = get_llm_provider()
    action = await llm.decide_next_action(goal, last_action, page_state)
"""

from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider

__all__ = ["LLMProvider", "get_llm_provider"]
