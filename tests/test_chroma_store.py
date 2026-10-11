"""Real local database checks using tiny known vectors and no model downloads."""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("chromadb")

from app.schemas.chunks import Chunk
from app.schemas.embeddings import EmbeddedChunk, EmbeddingInfo, EmbeddingResult
from app.schemas.metadata import SourceMetadata
from app.schemas.search import SearchFilters
from app.search.chroma_store import ChromaVectorStore


def example(folder="First", run=None) -> EmbeddingResult:
    info = EmbeddingInfo(
        provider="test",
        model="test",
        revision="fixed",
        dimensions=2,
        max_tokens=100,
        library_version="test",
    )
    source = SourceMetadata(
        discovery_id=run or uuid4(),
        folder_name=folder,
        file_name="bid.pdf",
        file_type="pdf",
        file_path=Path("/example/bid.pdf"),
        relative_path=Path("bid.pdf"),
    )
    records = []
    for index, (text, vector) in enumerate(
        [("Delivery within 45 days", [1.0, 0.0]), ("Warranty three years", [0.0, 1.0])]
    ):
        chunk = Chunk(
            chunk_id=uuid4(),
            source=source,
            page_number=index + 1,
            block_index=index,
            start_char=0,
            end_char=len(text),
            text=text,
        )
        records.append(EmbeddedChunk(chunk=chunk, vector=vector))
    return EmbeddingResult(info=info, embeddings=records)


def test_search_and_filters_preserve_complete_chunks(tmp_path: Path) -> None:
    first, second = example(), example("Second")
    store = ChromaVectorStore(tmp_path, "test_chunks", first.info)
    store.upsert(first)
    store.upsert(second)
    assert store.count() == 4
    filters = SearchFilters(
        folder_name="First", discovery_id=first.embeddings[0].chunk.source.discovery_id
    )
    hits = store.search([1.0, 0.0], 5, filters)
    assert len(hits) == 2
    assert hits[0].chunk == first.embeddings[0].chunk
    assert hits[0].similarity == pytest.approx(1.0, abs=1e-5)
    assert store.search([1.0, 0.0], filters=SearchFilters(folder_name="Missing")) == []


def test_same_chunk_ids_upsert_and_new_upload_appends(tmp_path: Path) -> None:
    first = example()
    store = ChromaVectorStore(tmp_path, "test_chunks", first.info)
    store.upsert(first)
    store.upsert(first)
    assert store.count() == 2
    second = example()
    store.upsert(second)
    assert store.count() == 4
    assert (
        first.embeddings[0].chunk.source.discovery_id
        != second.embeddings[0].chunk.source.discovery_id
    )


def test_model_mismatch_rejected_before_write(tmp_path: Path) -> None:
    first = example()
    store = ChromaVectorStore(tmp_path, "test_chunks", first.info)
    store.upsert(first)
    changed = example()
    changed.info.revision = "other"
    with pytest.raises(ValueError, match="differs"):
        store.upsert(changed)
    with pytest.raises(ValueError, match="differs"):
        ChromaVectorStore(tmp_path, "test_chunks", changed.info)
    assert store.count() == 2


def test_restart_reads_saved_data(tmp_path: Path) -> None:
    first = example()
    script = """
import sys
from app.schemas.embeddings import EmbeddingResult
from app.search.chroma_store import ChromaVectorStore
result = EmbeddingResult.model_validate_json(sys.stdin.read())
store = ChromaVectorStore(sys.argv[1], 'test_chunks', result.info)
store.upsert(result)
"""
    subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        input=first.model_dump_json(),
        text=True,
        capture_output=True,
        check=True,
    )
    reopened = ChromaVectorStore(tmp_path, "test_chunks")
    assert reopened.count() == 2
    assert reopened.search([1.0, 0.0], 1)[0].chunk == first.embeddings[0].chunk


def test_missing_and_empty_index_and_invalid_query(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="index"):
        ChromaVectorStore(tmp_path / "missing", "test_chunks")
    store = ChromaVectorStore(tmp_path, "test_chunks", example().info)
    assert store.search([1.0, 0.0]) == []
    with pytest.raises(ValueError):
        store.search([1.0])
    with pytest.raises(ValueError):
        store.search([1.0, 0.0], 0)


def test_document_role_and_numeric_addendum_filters(tmp_path: Path) -> None:
    result = example()
    base, changed = result.embeddings
    base.chunk.source = base.chunk.source.model_copy(update={"doc_type": "rfp"})
    changed.chunk.source = changed.chunk.source.model_copy(
        update={"doc_type": "addendum", "addendum_number": 2}
    )
    store = ChromaVectorStore(tmp_path, "test_chunks", result.info)
    store.upsert(result)
    filters = SearchFilters(
        discovery_id=base.chunk.source.discovery_id, doc_type="addendum", addendum_number=2
    )
    hits = store.search([1.0, 0.0], 5, filters)
    assert [hit.chunk.chunk_id for hit in hits] == [changed.chunk.chunk_id]
    assert hits[0].chunk.source.addendum_number == 2
    assert store.search([1.0, 0.0], filters=SearchFilters(addendum_number=1)) == []
    assert store.search([1.0, 0.0], filters=SearchFilters(doc_type="rfp"))[0].chunk == base.chunk


def test_agent_tool_searches_each_selected_upload_in_real_store(tmp_path):
    from app.tools.document_search import SearchTool

    first, second, excluded = example("Bid1"), example("Bid2"), example("Unselected")
    store = ChromaVectorStore(tmp_path, "selected_chunks", first.info)
    for batch in [first, second, excluded]:
        store.upsert(batch)

    class Provider:
        info = first.info

        def embed_query(self, query):
            return [0.0, 1.0]

    ids = [batch.embeddings[0].chunk.source.discovery_id for batch in [first, second]]
    evidence = SearchTool(Provider(), store, ids).run({"query": "Warranty", "top_k": 1})
    assert [item["folder_name"] for item in evidence] == ["Bid1", "Bid2"]
    assert [item["discovery_id"] for item in evidence] == list(map(str, ids))
    assert all(item["text"] == "Warranty three years" for item in evidence)
