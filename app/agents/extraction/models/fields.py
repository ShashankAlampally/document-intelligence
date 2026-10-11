"""Extraction contracts; schemas describe data, not execution."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.extraction.models.field_catalog import FieldName


class FieldDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: FieldName
    value: str | None
    source_chunk_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    notes: str | None


class ExtractionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[FieldDraft]


class ExtractedField(BaseModel):
    value: str | None
    sources: list[dict]
    confidence: float
    notes: str | None


class ExtractionResult(BaseModel):
    status: Literal["completed", "error"]
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    validation_report: list[dict] = Field(default_factory=list)
    confidence_method: str = "Uncalibrated model estimate; missing values use 0"
    error: str | None = None
    trace: list[dict] = Field(default_factory=list)
