"""Embedding contract; other providers need not depend on Sentence Transformers."""

from typing import Protocol

from app.schemas.embeddings import EmbeddingInfo


class EmbeddingProvider(Protocol):
    @property
    def info(self) -> EmbeddingInfo: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


# Providers may also expose count_tokens(text) for pre-embedding chunk splitting.
# The count must include special tokens, matching embed_documents preprocessing.
