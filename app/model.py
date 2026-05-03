from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, Field

class ActionType(str, Enum): 
    GOTO = "goto"
    CLICK = "click"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"
    SELECT = "select"
    BACK = "back"
    HOVER = "hover"
    UPLOAD_FILE = "upload_file"
    CONFIRM_HUMAN_CHECKPOINT = "confirm_human_checkpoint"
    SCREENSHOT = "screenshot"


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

class SelectAction(BaseModel):
    type: Literal[ActionType.SELECT]
    target: str = Field(..., description="The target element selector")
    value: str = Field(..., description="The value to select")

class BackAction(BaseModel):
    type: Literal[ActionType.BACK]

class HoverAction(BaseModel):
    type: Literal[ActionType.HOVER]
    target: str = Field(..., description="The target element to hover")

class UploadFileAction(BaseModel):
    type: Literal[ActionType.UPLOAD_FILE]
    target: str = Field(..., description="The file input selector")
    path: str = Field(..., description="The local file path to upload")

class ConfirmHumanCheckpoint(BaseModel):
    type: Literal[ActionType.CONFIRM_HUMAN_CHECKPOINT]
    reason: str = Field(..., description="Reason for human approval")

class ScreenshotAction(BaseModel):
    type: Literal[ActionType.SCREENSHOT]
    name: str = Field(default="step", description="Screenshot file name")

Action = Union[
    GotoAction, ClickAction, TypeAction, PressAction,
    ScrollAction, SelectAction, BackAction, HoverAction,
    UploadFileAction, ConfirmHumanCheckpoint, ScreenshotAction,
]