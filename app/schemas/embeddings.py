"""Validated embedding results linked to chunks and a specific model space."""

import math

from pydantic import BaseModel, Field, FiniteFloat, model_validator

from app.schemas.chunks import Chunk


class EmbeddingInfo(BaseModel):
    provider: str
    model: str
    revision: str
    dimensions: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    normalized: bool = True
    query_prefix: str = ""
    library_version: str


class EmbeddedChunk(BaseModel):
    chunk: Chunk
    vector: list[FiniteFloat] = Field(min_length=1)


class QueryEmbedding(BaseModel):
    text: str = Field(min_length=1)
    vector: list[FiniteFloat] = Field(min_length=1)


class EmbeddingResult(BaseModel):
    info: EmbeddingInfo
    embeddings: list[EmbeddedChunk] = Field(default_factory=list)
    query: QueryEmbedding | None = None

    @model_validator(mode="after")
    def check_vectors(self) -> "EmbeddingResult":
        records = [*self.embeddings, *([self.query] if self.query else [])]
        for record in records:
            if len(record.vector) != self.info.dimensions:
                raise ValueError("Vector dimensions do not match model metadata")
            norm = math.sqrt(sum(value * value for value in record.vector))
            if norm == 0 or not math.isfinite(norm):
                raise ValueError("Embedding vector must have a finite, nonzero norm")
            if self.info.normalized and not math.isclose(norm, 1.0, abs_tol=1e-4):
                raise ValueError("Expected a unit-normalized embedding vector")
        ids = [record.chunk.chunk_id for record in self.embeddings]
        if len(set(ids)) != len(ids):
            raise ValueError("Embedding input contains duplicate chunk IDs")
        return self
