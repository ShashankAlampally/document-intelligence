"""Shared request and results for the first main graph."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.agents.extraction.models.fields import ExtractionResult
from app.agents.planner.models.task import TaskChoice
from app.agents.qa.models.answers import QuestionAnswer


class MainState(BaseModel):
    request: str
    discovery_id: UUID | None = None
    discovery_ids: list[UUID] = Field(default_factory=list)
    choice: TaskChoice | None = None
    qa_result: QuestionAnswer | None = None
    extraction_result: ExtractionResult | None = None
    error: str | None = None
    trace: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_selection(self):
        from app.tools.selected_uploads import selected_uploads

        self.discovery_ids = selected_uploads(self.discovery_ids or self.discovery_id or [])
        self.discovery_id = self.discovery_ids[0] if len(self.discovery_ids) == 1 else None
        return self
