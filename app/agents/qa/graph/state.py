"""Information carried between Q&A graph nodes during one request."""

from pydantic import Field

from app.agents.qa.models.answers import AnswerDraft, AnswerOrSearch
from app.agents.shared.state import ToolState


class WorkflowState(ToolState):
    draft: AnswerDraft | None = None
    decision: AnswerOrSearch | None = None
    max_followup_queries: int = Field(default=6, ge=1, le=10)
    missing_information: list[str] = Field(default_factory=list)
