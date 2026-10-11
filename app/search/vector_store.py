"""Storage interface shared by indexing and retrieval."""

from typing import Protocol

from app.schemas.chunks import Chunk
from app.schemas.embeddings import EmbeddingInfo, EmbeddingResult
from app.schemas.search import SearchFilters, SearchHit


class VectorStore(Protocol):
    info: EmbeddingInfo

    def upsert(self, result: EmbeddingResult) -> int: ...

    def count(self) -> int: ...

    def list_chunks(self, filters: SearchFilters | None = None) -> list[Chunk]: ...

    def search(
        self, vector: list[float], top_k: int, filters: SearchFilters | None = None
    ) -> list[SearchHit]: ...
