"""Common input, retrieved evidence, errors and traces for specialist agents."""

from pydantic import BaseModel, Field


class ToolState(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    search_requests: list[dict] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    search_top_k: int = Field(default=3, ge=1, le=20)
    max_evidence_chunks: int | None = Field(default=None, ge=1)
    max_evidence_chars: int | None = Field(default=None, ge=2)
    evidence: list[dict] = Field(default_factory=list)
    error: str | None = None
    trace: list[dict] = Field(default_factory=list)
