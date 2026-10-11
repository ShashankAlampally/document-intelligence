"""Validate embedding service output with a small provider, without model downloads."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.chunks import Chunk
from app.schemas.embeddings import EmbeddingInfo, EmbeddingResult
from app.schemas.metadata import SourceMetadata
from app.search.embeddings import embed_chunks


class TestProvider:
    __test__ = False
    info = EmbeddingInfo(
        provider="test",
        model="test",
        revision="test",
        dimensions=2,
        max_tokens=100,
        normalized=True,
        library_version="test",
    )

    def __init__(self):
        self.received = []
        self.vectors = [[1.0, 0.0], [0.0, 1.0]]

    def embed_documents(self, texts):
        self.received = texts
        return self.vectors[: len(texts)]

    def embed_query(self, text):
        return [0.6, 0.8]


def chunks() -> list[Chunk]:
    source = SourceMetadata(
        discovery_id=uuid4(),
        folder_name="Example",
        file_name="bid.pdf",
        file_type="pdf",
        file_path=Path("/example/bid.pdf"),
        relative_path=Path("bid.pdf"),
    )
    return [
        Chunk(
            chunk_id=uuid4(),
            source=source,
            page_number=1,
            block_index=i,
            start_char=0,
            end_char=len(text),
            text=text,
        )
        for i, text in enumerate(["Delivery in 45 days", "Warranty three years"])
    ]


def test_vectors_keep_input_order_source_and_model_identity() -> None:
    original = chunks()
    provider = TestProvider()
    result = embed_chunks(original, provider, "When is delivery?")
    assert provider.received == [chunk.text for chunk in original]
    assert [record.chunk.chunk_id for record in result.embeddings] == [c.chunk_id for c in original]
    assert result.embeddings[0].vector == [1.0, 0.0]
    assert result.query.vector == [0.6, 0.8]
    assert result.info == provider.info
    assert EmbeddingResult.model_validate_json(result.model_dump_json()) == result
    result.embeddings[0].chunk.source.folder_name = "Changed"
    assert original[0].source.folder_name == "Example"


@pytest.mark.parametrize(
    "vectors",
    [
        [[1.0, 0.0]],
        [[1.0], [1.0]],
        [[float("nan"), 0.0], [0.0, 1.0]],
        [[float("inf"), 0.0], [0.0, 1.0]],
        [[0.0, 0.0], [0.0, 1.0]],
        [[2.0, 0.0], [0.0, 1.0]],
    ],
)
def test_invalid_provider_outputs_are_rejected(vectors) -> None:
    provider = TestProvider()
    provider.vectors = vectors
    with pytest.raises(ValueError):
        embed_chunks(chunks(), provider)


def test_duplicate_ids_and_empty_queries_are_rejected() -> None:
    original = chunks()
    with pytest.raises(ValueError, match="duplicate"):
        embed_chunks([original[0], original[0]], TestProvider())
    with pytest.raises(ValueError, match="Query"):
        embed_chunks(original, TestProvider(), "  ")


def test_empty_input_returns_no_embeddings() -> None:
    assert embed_chunks([], TestProvider()).embeddings == []


def test_token_counting_provider_receives_only_fitted_chunks():
    class DenseProvider(TestProvider):
        def count_tokens(self, text):
            return len(text) + 2

        def embed_documents(self, texts):
            assert all(self.count_tokens(text) <= self.info.max_tokens for text in texts)
            self.received = texts
            return [[1.0, 0.0] for _ in texts]

    original = chunks()[0].model_copy(update={"text": "x" * 250, "end_char": 250})
    provider = DenseProvider()
    result = embed_chunks([original], provider)
    assert len(result.embeddings) > 1
    assert sum(len(text) for text in provider.received) >= 250
    assert original.text == "x" * 250
