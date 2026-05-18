from enum import Enum
from tokenize import String
from typing import Any, Literal, Union

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    GOTO = "goto"
    CLICK = "click"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    DONE = "done"


class GotoAction(BaseModel):
    type: Literal[ActionType.GOTO]
    url: str = Field(..., description="The URL to navigate to")


class ClickAction(BaseModel):
    type: Literal[ActionType.CLICK]
    target: str = Field(..., description="The target to click on")


class TypeAction(BaseModel):
    type: Literal[ActionType.TYPE]
    target: str = Field(..., description="The target to type on")
    text: str = Field(..., description="The text to type")


class PressAction(BaseModel):
    type: Literal[ActionType.PRESS]
    key: str = Field(..., description="The key to press")


class ScrollAction(BaseModel):
    type: Literal[ActionType.SCROLL]
    direction: str = Field(..., description="Direction to scroll: up or down")
    amount: int = Field(default=300, description="Pixels to scroll")


class ScreenshotAction(BaseModel):
    type: Literal[ActionType.SCREENSHOT]
    name: str = Field(default="step", description="Screenshot file name")


class DoneAction(BaseModel):
    type: Literal[ActionType.DONE]
    result: str = Field(..., description="Summary of what was accomplished")


Action = (
    GotoAction
    | ClickAction
    | TypeAction
    | PressAction
    | ScrollAction
    | ScreenshotAction
    | DoneAction
)


class DecideRequest(BaseModel):
    goal: str
    memory: str | None
    recent_steps: list[dict[str, Any]] | None
    page_state: dict[str, Any] | None


class AgentOutput(BaseModel):
    evaluation: str = Field(..., max_length=200)
    memory: str = Field(..., max_length=600)
    next_goal: str = Field(..., max_length=150)
    action: Action


class InteractRequest(BaseModel):
    prompt: str = ""


class ExtractRequest(BaseModel):
    run_id: str = Field(..., description="Run identifier to extract results from")
    schema_name: str = Field(
        default="default", description="Named extraction schema to apply"
    )

