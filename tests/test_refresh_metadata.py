"""Refresh real stored metadata while preserving vectors and isolating uploads."""

from uuid import uuid4

import pytest

pytest.importorskip("chromadb")

from test_chroma_store import example

from app.schemas.search import SearchFilters
from app.search.chroma_store import ChromaVectorStore
from app.search.refresh_metadata import refresh_metadata


def test_refresh_preserves_ids_vectors_text_and_other_uploads(tmp_path):
    first, other = example(), example("Other")
    for record in first.embeddings:
        record.chunk.source.file_name = "Addendum 2.pdf"
    store = ChromaVectorStore(tmp_path, "test_chunks", first.info)
    store.upsert(first)
    store.upsert(other)
    before = store.collection.get(include=["embeddings", "documents", "metadatas"])
    upload_id = first.embeddings[0].chunk.source.discovery_id
    assert refresh_metadata(store, upload_id) == 2
    after = store.collection.get(include=["embeddings", "documents", "metadatas"])
    assert before["ids"] == after["ids"]
    assert before["documents"] == after["documents"]
    assert before["embeddings"].tolist() == after["embeddings"].tolist()
    assert store.count() == 4
    filters = SearchFilters(discovery_id=upload_id, doc_type="addendum", addendum_number=2)
    assert len(store.search([1.0, 0.0], 5, filters)) == 2
    for old, new in zip(before["metadatas"], after["metadatas"]):
        if old["discovery_id"] != str(upload_id):
            assert old == new
    assert refresh_metadata(store, upload_id) == 0


def test_unknown_upload_fails_without_changes(tmp_path):
    result = example()
    store = ChromaVectorStore(tmp_path, "test_chunks", result.info)
    store.upsert(result)
    with pytest.raises(ValueError, match="No chunks found"):
        refresh_metadata(store, uuid4())
    assert store.count() == 2
