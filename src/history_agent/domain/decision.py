from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

class DecisionType(str, Enum):
    TOOL = "tool"
    FINAL = "final"

class Decision(BaseModel):
    type: Literal["tool", "final"] = Field(
        description="The next action. 'tool' to call a tool, 'final' to answer the user."
    )

    reason: str = Field(
        description="Brief reason for the decision."
    )

    tool_name: str | None = Field(
        default=None,
        description="Tool name when type is 'tool'."
    )

    tool_args: dict[str, Any] | None = Field(
        default=None,
        description="Arguments for the selected tool."
    )

    answer: str | None = Field(
        default=None,
        description="Final answer when type is 'final'."
    )
