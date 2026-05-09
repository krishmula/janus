"""Gemini-backed LLM provider."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

from app.llm.base import LLMProvider
from app.llm.prompts import SYSTEM_PROMPT
from app.llm.schemas import _ACTION_RESPONSE_SCHEMA

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Gemini-backed LLM provider using ``google-genai``.

    Expects ``GEMINI_API_KEY`` in the environment (or passed to the
    constructor).  Optionally respects ``GEMINI_MODEL`` (defaults to
    ``gemini-2.5-flash``).
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY env var "
                "or pass api_key to GeminiProvider."
            )

        self._model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        self._client = genai.Client(api_key=self._api_key)

    async def _generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Call Gemini and return parsed JSON.

        Runs the synchronous SDK inside ``asyncio.to_thread`` so the call
        doesn't block the event loop.
        """
        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_json_schema=response_schema,
        )

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        def _call() -> str:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=full_prompt,
                config=generation_config,
            )
            # Safety filters or empty responses can come back with no text.
            if not response.text:
                raise RuntimeError(
                    "Gemini returned an empty response (possible safety filter)."
                )
            return response.text

        try:
            raw_text = await asyncio.to_thread(_call)
        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            raise

        try:
            parsed: dict[str, Any] = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse Gemini response as JSON. "
                "Raw text (first 500 chars): %s",
                raw_text[:500],
            )
            raise RuntimeError("Invalid JSON from Gemini") from exc

        return parsed

    async def decide_next_action(
        self,
        goal: str,
        last_action: dict[str, Any] | None,
        page_state: dict[str, Any],
    ) -> dict[str, Any]:
        user_prompt = (
            f"Goal: {goal}\n"
            f"Last action: {json.dumps(last_action)}\n"
            f"Page state: {json.dumps(page_state)}\n"
            f"Decide the next single action now."
        )
        response = await self._generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=_ACTION_RESPONSE_SCHEMA,
            temperature=0.1,  # deterministic for step execution
        )
        logger.debug("Decided next action: %s", response.get("type"))
        return response
