from __future__ import annotations

import pydantic
import pytest
from pydantic import TypeAdapter

from app.model import (
    Action,
    ActionType,
    ClickAction,
    DoneAction,
    ExtractRequest,
    GotoAction,
    InteractRequest,
    PressAction,
    ScreenshotAction,
    ScrollAction,
    TypeAction,
)

_action_adapter = TypeAdapter(Action)


class TestActionTypeEnum:
    def test_has_7_values(self):
        values = {e.value for e in ActionType}
        assert values == {
            "goto", "click", "type", "press",
            "scroll", "screenshot", "done",
        }

    def test_extract_not_present(self):
        assert "extract" not in {e.value for e in ActionType}


class TestGotoAction:
    def test_requires_url(self):
        a = GotoAction(type="goto", url="https://example.com")
        assert a.url == "https://example.com"

    def test_rejects_missing_url(self):
        with pytest.raises(pydantic.ValidationError):
            GotoAction(type="goto")


class TestClickAction:
    def test_requires_target(self):
        a = ClickAction(type="click", target=".titleline > a")
        assert a.target == ".titleline > a"

    def test_rejects_missing_target(self):
        with pytest.raises(pydantic.ValidationError):
            ClickAction(type="click")


class TestTypeAction:
    def test_requires_target_and_text(self):
        a = TypeAction(type="type", target="input", text="hello")
        assert a.target == "input"
        assert a.text == "hello"

    def test_rejects_missing_text(self):
        with pytest.raises(pydantic.ValidationError):
            TypeAction(type="type", target="input")


class TestPressAction:
    def test_requires_key(self):
        a = PressAction(type="press", key="Enter")
        assert a.key == "Enter"

    def test_rejects_missing_key(self):
        with pytest.raises(pydantic.ValidationError):
            PressAction(type="press")


class TestScrollAction:
    def test_default_amount(self):
        a = ScrollAction(type="scroll", direction="down")
        assert a.amount == 300

    def test_custom_amount(self):
        a = ScrollAction(type="scroll", direction="up", amount=500)
        assert a.amount == 500


class TestScreenshotAction:
    def test_default_name(self):
        a = ScreenshotAction(type="screenshot")
        assert a.name == "step"

    def test_custom_name(self):
        a = ScreenshotAction(type="screenshot", name="final")
        assert a.name == "final"


class TestDoneAction:
    def test_requires_result(self):
        a = DoneAction(type="done", result="task completed")
        assert a.result == "task completed"

    def test_rejects_missing_result(self):
        with pytest.raises(pydantic.ValidationError):
            DoneAction(type="done")


class TestActionUnion:
    def test_accepts_goto(self):
        a = _action_adapter.validate_python({"type": "goto", "url": "https://example.com"})
        assert isinstance(a, GotoAction)

    def test_accepts_click(self):
        a = _action_adapter.validate_python({"type": "click", "target": "a"})
        assert isinstance(a, ClickAction)

    def test_accepts_type(self):
        a = _action_adapter.validate_python({"type": "type", "target": "input", "text": "hi"})
        assert isinstance(a, TypeAction)

    def test_accepts_press(self):
        a = _action_adapter.validate_python({"type": "press", "key": "Enter"})
        assert isinstance(a, PressAction)

    def test_accepts_scroll(self):
        a = _action_adapter.validate_python({"type": "scroll", "direction": "down"})
        assert isinstance(a, ScrollAction)

    def test_accepts_screenshot(self):
        a = _action_adapter.validate_python({"type": "screenshot"})
        assert isinstance(a, ScreenshotAction)

    def test_accepts_done(self):
        a = _action_adapter.validate_python({"type": "done", "result": "done"})
        assert isinstance(a, DoneAction)

    def test_rejects_invalid_type(self):
        with pytest.raises(pydantic.ValidationError):
            _action_adapter.validate_python({"type": "extract"})

    def test_rejects_extract(self):
        with pytest.raises(pydantic.ValidationError):
            _action_adapter.validate_python({"type": "extract", "target": "data"})


class TestInteractRequest:
    def test_default_prompt(self):
        r = InteractRequest()
        assert r.prompt == ""

    def test_custom_prompt(self):
        r = InteractRequest(prompt="test prompt")
        assert r.prompt == "test prompt"


class TestExtractRequest:
    def test_requires_run_id(self):
        with pytest.raises(pydantic.ValidationError):
            ExtractRequest()

    def test_default_schema_name(self):
        r = ExtractRequest(run_id="abc-123")
        assert r.schema_name == "default"

    def test_custom_schema_name(self):
        r = ExtractRequest(run_id="abc-123", schema_name="custom")
        assert r.schema_name == "custom"
