"""Indexing reports and cited dense-search results."""

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, FiniteFloat

from app.schemas.chunks import Chunk, ChunkSettings
from app.schemas.documents import ParsingIssue
from app.schemas.embeddings import EmbeddingInfo
from app.schemas.metadata import DocumentType


class SearchFilters(BaseModel):
    folder_name: str | None = None
    discovery_id: UUID | None = None
    file_name: str | None = None
    doc_type: DocumentType | None = None
    addendum_number: int | None = Field(default=None, ge=1)
    table_id: UUID | None = None


class SearchHit(BaseModel):
    chunk: Chunk
    similarity: FiniteFloat | None = None  # Only the vector cosine similarity.
    retrieval_score: FiniteFloat | None = None  # Weighted RRF, not confidence.
    rerank_score: FiniteFloat | None = None  # Relevance, not answer confidence.
    keyword_score: FiniteFloat | None = None
    vector_rank: int | None = Field(default=None, ge=1)
    keyword_rank: int | None = Field(default=None, ge=1)


class FileIndexReport(BaseModel):
    relative_path: Path
    chunk_count: int = Field(ge=0)
    issues: list[ParsingIssue] = Field(default_factory=list)


class IndexReport(BaseModel):
    discovery_id: UUID
    folder_name: str
    model: EmbeddingInfo
    chunk_settings: ChunkSettings
    files: list[FileIndexReport]
    stored_chunks: int = Field(ge=0)
    collection_count: int = Field(ge=0)
