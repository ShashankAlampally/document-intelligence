"""Folder indexing keeps old records and reports file failures."""

from pathlib import Path

import pytest

from app.schemas.embeddings import EmbeddingInfo
from app.search.indexer import index_folder


class Provider:
    info = EmbeddingInfo(
        provider="test",
        model="test",
        revision="fixed",
        dimensions=2,
        max_tokens=100,
        library_version="test",
    )

    def __init__(self):
        self.batches = []

    def embed_documents(self, texts):
        self.batches.append(texts)
        return [[1.0, 0.0] for _ in texts]


class Store:
    def __init__(self):
        self.records = {}

    def upsert(self, result):
        self.records.update({record.chunk.chunk_id: record for record in result.embeddings})
        return len(result.embeddings)

    def count(self):
        return len(self.records)


def test_adding_folder_only_embeds_new_input_and_retains_errors(tmp_path: Path) -> None:
    first = tmp_path / "First"
    first.mkdir()
    (first / "notice.html").write_text("<p>First folder terms</p>")
    second = tmp_path / "Second"
    second.mkdir()
    (second / "notice.html").write_text("<p>Second folder terms</p>")
    (second / "broken.pdf").write_text("Not a PDF")
    provider, store = Provider(), Store()
    first_report = index_folder(first, provider, store)
    old_ids = set(store.records)
    second_report = index_folder(second, provider, store)
    assert first_report.collection_count == 1
    assert second_report.collection_count == 2
    assert old_ids.issubset(store.records)
    assert provider.batches == [["First folder terms"], ["Second folder terms"]]
    assert second_report.discovery_id != first_report.discovery_id
    failed = next(file for file in second_report.files if file.relative_path.name == "broken.pdf")
    assert failed.chunk_count == 0
    assert failed.issues[0].severity == "error"


def test_textless_folder_does_not_write_vectors(tmp_path: Path) -> None:
    (tmp_path / "notice.html").write_text("<body></body>")
    provider, store = Provider(), Store()
    with pytest.raises(ValueError, match="No text chunks"):
        index_folder(tmp_path, provider, store)
    assert store.count() == 0
    assert provider.batches == []


def test_report_counts_token_splits_instead_of_original_character_chunks(tmp_path):
    class TokenProvider(Provider):
        def count_tokens(self, text):
            return len(text) + 2

        def embed_documents(self, texts):
            assert all(self.count_tokens(text) <= self.info.max_tokens for text in texts)
            return super().embed_documents(texts)

    (tmp_path / "dense.html").write_text("<p>" + "X123_" * 150 + "</p>")
    provider, store = TokenProvider(), Store()
    report = index_folder(tmp_path, provider, store)
    assert report.stored_chunks > 1
    assert report.files[0].chunk_count == report.stored_chunks == store.count()
