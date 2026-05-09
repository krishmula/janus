from __future__ import annotations

from app.llm.schemas import _ACTION_RESPONSE_SCHEMA


class TestActionResponseSchema:
    def test_done_in_enum(self):
        actions = _ACTION_RESPONSE_SCHEMA["properties"]["type"]["enum"]
        assert "done" in actions

    def test_extract_not_in_enum(self):
        actions = _ACTION_RESPONSE_SCHEMA["properties"]["type"]["enum"]
        assert "extract" not in actions

    def test_schema_structure(self):
        assert _ACTION_RESPONSE_SCHEMA["type"] == "object"
        assert "properties" in _ACTION_RESPONSE_SCHEMA
        assert "type" in _ACTION_RESPONSE_SCHEMA["required"]

    def test_all_7_action_types_in_enum(self):
        actions = set(_ACTION_RESPONSE_SCHEMA["properties"]["type"]["enum"])
        expected = {"goto", "click", "type", "press", "scroll", "screenshot", "done"}
        assert actions == expected
