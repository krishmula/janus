"""Provider factory — creates LLMProvider instances by name."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.llm.base import LLMProvider

_PROVIDERS: dict[str, type["LLMProvider"]] = {}


def _register_defaults() -> None:
    """Lazily import and register built-in providers to avoid heavy imports
    at module load time."""
    from app.llm.gemini import GeminiProvider

    _PROVIDERS.setdefault("gemini", GeminiProvider)


def get_llm_provider(provider_name: str | None = None) -> "LLMProvider":
    """Return a configured LLMProvider instance.

    Reads ``LLM_PROVIDER`` from the environment when *provider_name* is not
    supplied.  Defaults to ``gemini``.
    """
    _register_defaults()
    name = (provider_name or os.getenv("LLM_PROVIDER", "gemini")).lower()
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider: {name!r}. "
            f"Available: {', '.join(_PROVIDERS)}"
        )
    return cls()
