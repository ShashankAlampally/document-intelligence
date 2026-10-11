"""Public HTTP contracts for folder processing and bid questions.

These contracts intentionally stay separate from internal agent state.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.retrieval import SearchTuning


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProcessingJob(ApiModel):
    id: UUID
    status: Literal["processing", "ready", "failed"]
    session_id: UUID | None = None
    discovery_id: UUID | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def ready_requires_discovery_id(self) -> "ProcessingJob":
        if self.discovery_id is not None and self.session_id is not None:
            if self.discovery_id != self.session_id:
                raise ValueError("session_id is a legacy alias for discovery_id")
        self.discovery_id = self.discovery_id or self.session_id
        self.session_id = self.discovery_id
        if self.status == "ready" and self.session_id is None:
            raise ValueError("A ready job must include discovery_id (or legacy session_id)")
        return self


class DocumentQuery(ApiModel, SearchTuning):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    file_name: str | None = Field(default=None, min_length=1, max_length=500)
    doc_type: Literal["bid_page", "rfp", "addendum", "specs", "affidavit"] | None = None
    addendum_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def trim_question(self) -> "DocumentQuery":
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("Question must contain non-whitespace text")
        return self


class SelectedDocumentQuery(DocumentQuery):
    discovery_ids: list[UUID] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_uploads(self) -> "SelectedDocumentQuery":
        self.discovery_ids = list(dict.fromkeys(self.discovery_ids))
        return self


class SourcePassage(ApiModel):
    table_id: UUID | None = None
    table_complete: bool | None = None
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    discovery_id: UUID | None = None
    folder_name: str | None = None
    file: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    text: str
    chunk_id: str | None = None
    similarity: float | None = None
    retrieval_score: float | None = None
    rerank_score: float | None = None
    keyword_score: float | None = None
    vector_rank: int | None = Field(default=None, ge=1)
    keyword_rank: int | None = Field(default=None, ge=1)


class DocumentReply(ApiModel):
    answer: str
    sources: list[SourcePassage] = Field(default_factory=list)


class ApiError(ApiModel):
    detail: str
    code: str


class RequestError(ApiModel):
    detail: str


WORKSPACE_RESPONSES = {
    status: {"model": RequestError, "description": description}
    for status, description in {
        404: "Job or indexed upload not found",
        413: "Upload limit exceeded",
        429: "Model provider rate limit",
        502: "Agent failed to produce a valid response",
        503: "Core service configuration or dependency failure",
        504: "Model provider timeout",
    }.items()
}
WORKSPACE_RESPONSES[501] = {"model": ApiError, "description": "Injected adapter is not connected"}
