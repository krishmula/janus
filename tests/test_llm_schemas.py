from __future__ import annotations

from app.llm.schemas import _AGENT_OUTPUT_SCHEMA

_action_props = _AGENT_OUTPUT_SCHEMA["properties"]["action"]["properties"]
_action_enum = _action_props["type"]["enum"]


class TestAgentOutputSchema:
    def test_outer_has_four_required_fields(self):
        assert set(_AGENT_OUTPUT_SCHEMA["required"]) == {
            "evaluation", "memory", "next_goal", "action"
        }

    def test_evaluation_has_max_length_200(self):
        assert _AGENT_OUTPUT_SCHEMA["properties"]["evaluation"]["maxLength"] == 200

    def test_memory_has_max_length_600(self):
        assert _AGENT_OUTPUT_SCHEMA["properties"]["memory"]["maxLength"] == 600

    def test_next_goal_has_max_length_150(self):
        assert _AGENT_OUTPUT_SCHEMA["properties"]["next_goal"]["maxLength"] == 150

    def test_action_has_all_7_types(self):
        assert set(_action_enum) == {
            "goto", "click", "type", "press", "scroll", "screenshot", "done"
        }

    def test_done_in_action_enum(self):
        assert "done" in _action_enum

    def test_extract_not_in_action_enum(self):
        assert "extract" not in _action_enum

    def test_action_type_is_required(self):
        assert "type" in _AGENT_OUTPUT_SCHEMA["properties"]["action"]["required"]
