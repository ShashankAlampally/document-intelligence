"""The main graph chooses a task, not a specialist's search tool."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class TaskChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Literal["qa", "extraction", "reply"]
    message: str | None
