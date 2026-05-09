"""JSON schemas for structured LLM output (Gemini JSON mode, etc.)."""

from typing import Any

_ACTION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "goto",
                "click",
                "type",
                "press",
                "scroll",
                "screenshot",
                "done",
            ],
        },
        "url": {"type": "string"},
        "target": {"type": "string"},
        "text": {"type": "string"},
        "key": {"type": "string"},
        "direction": {"type": "string", "enum": ["up", "down"]},
        "amount": {"type": "integer"},
        "name": {"type": "string"},
        "result": {"type": "string"},
    },
    "required": ["type"],
}
