"""Structured answer from the LLM and the result returned to callers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["found", "not_found"]
    answer: str
    source_chunk_ids: list[str]


class EvidenceCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_part: str
    status: Literal["supported", "missing", "explicitly_unavailable"]
    source_chunk_ids: list[str]


class AnswerOrSearch(AnswerDraft):
    action: Literal["answer", "search_more"]
    search_queries: list[str]
    missing_information: list[str]
    coverage: list[EvidenceCoverage] = Field(default_factory=list)


class QuestionAnswer(BaseModel):
    status: Literal["found", "not_found", "direct_response", "error"]
    answer: str
    sources: list[dict] = Field(default_factory=list)
    error: str | None = None
    trace: list[dict] = Field(default_factory=list)
