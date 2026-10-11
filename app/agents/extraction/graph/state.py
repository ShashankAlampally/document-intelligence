"""Shared tool-loop state plus the extraction agent's field draft."""

from pydantic import Field

from app.agents.extraction.models.fields import ExtractionDraft
from app.agents.extraction.models.validation import ValidationReport
from app.agents.shared.state import ToolState


class ExtractionState(ToolState):
    requested_fields: list[str] = Field(default_factory=list)
    draft: ExtractionDraft | None = None
    validation: ValidationReport | None = None
    retry_fields: list[str] = Field(default_factory=list)
    correction_attempts: int = 0
