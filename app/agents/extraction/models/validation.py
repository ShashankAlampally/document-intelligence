"""Decisions made by the Extraction Validator Agent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.agents.extraction.models.field_catalog import FieldName


class FieldValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: FieldName
    decision: Literal["accepted", "needs_evidence", "incorrect"]
    reason: str


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[FieldValidation]
