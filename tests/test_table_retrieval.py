"""Lossless table indexing and retrieval using temporary Chroma, without an LLM."""

import json
from uuid import uuid4, uuid5

import pytest
from test_chroma_store import example
from test_chunker import make_document

from app.agents.shared.retrieve_evidence import retrieve_evidence
from app.agents.shared.state import ToolState
from app.schemas.chunks import Chunk, ChunkSettings
from app.schemas.content import TableBlock
from app.schemas.embeddings import EmbeddedChunk, EmbeddingResult
from app.schemas.retrieval import HybridOptions
from app.schemas.search import SearchFilters, SearchHit
from app.search.chroma_store import ChromaVectorStore
from app.search.chunker import chunk_document
from app.search.service import search_documents
from app.search.table_context import expand_tables
from app.search.token_safe_chunks import fit_chunks_to_tokens


def table_document(file_type="pdf"):
    document = make_document(file_type)
    location = {"page_number": 1} if file_type == "pdf" else {"section": "section-2"}
    document.tables = [
        TableBlock(
            **location,
            headers=["Item", "Quantity"],
            rows=[["Laptop\nTier 1", "30"], [None, "10"], ["Repeated", "2"], ["Repeated", "2"]],
        )
    ]
    return document


def parts(document):
    return [
        c
        for c in chunk_document(document, ChunkSettings(max_chars=85, overlap_chars=10)).chunks
        if c.content_type == "table"
    ]


@pytest.mark.parametrize("file_type", ["pdf", "html"])
def test_rows_and_text_provenance_survive_serialization(file_type):
    document = table_document(file_type)
    result = chunk_document(document, ChunkSettings(max_chars=85, overlap_chars=10))
    tables = [c for c in result.chunks if c.content_type == "table"]
    assert len(tables) > 1
    assert [row for c in tables for row in c.table_rows] == document.tables[0].rows
    assert [n for c in tables for n in range(c.table_row_start, c.table_row_end + 1)] == [
        1,
        2,
        3,
        4,
    ]
    for chunk in result.chunks:
        assert Chunk.model_validate_json(chunk.model_dump_json()) == chunk
        if chunk.content_type == "text":
            identity = (
                f"{document.source.relative_path.as_posix()}|native|text|{chunk.block_index}|"
                f"{chunk.start_char}|{chunk.end_char}|{chunk.text}"
            )
            assert chunk.chunk_id == uuid5(document.source.discovery_id, identity)
    assert document.tables[0].table_id is None


def test_table_ids_are_stable_and_scoped_to_upload_file_page_and_table():
    document = table_document()
    identity = parts(document)[0].table_id
    assert parts(document)[0].table_id == identity
    for change in ["upload", "file", "page", "table"]:
        changed = document.model_copy(deep=True)
        if change == "upload":
            changed.source.discovery_id = uuid4()
        elif change == "file":
            changed.source.relative_path = changed.source.relative_path.with_name("other.pdf")
        elif change == "page":
            changed.tables[0].page_number = 2
        else:
            changed.tables.insert(0, changed.tables[0].model_copy(deep=True))
        candidate = parts(changed)[-1] if change == "table" else parts(changed)[0]
        assert candidate.table_id != identity


@pytest.mark.parametrize("max_tokens", [70, 15])
def test_token_splitting_preserves_full_rows_for_reconstruction(max_tokens):
    document = table_document()
    document.tables[0].rows[0][0] = "Large row " * 100
    original = parts(document)
    fitted = fit_chunks_to_tokens(original, len, max_tokens)
    assert all(len(c.text) <= max_tokens for c in fitted)
    assert len({c.chunk_id for c in fitted}) == len(fitted)

    class Store:
        def list_chunks(self, filters):
            return fitted

    hits = expand_tables([SearchHit(chunk=fitted[0])], Store())
    assert hits[0].chunk.table_complete is True
    assert hits[0].chunk.table_rows == document.tables[0].rows
    assert set(hits[0].chunk.source_chunk_ids) == {c.chunk_id for c in fitted}


@pytest.mark.parametrize("options", [None, HybridOptions()])
def test_real_store_returns_only_matched_parts_and_isolates_uploads(tmp_path, options, monkeypatch):
    document = table_document()
    document.text_blocks = []  # Tables remain searchable even without a text block.
    chunks = parts(document)
    info = example().info
    store = ChromaVectorStore(tmp_path, "table_test", info)
    other = table_document()
    other.tables[0].rows = [["Other upload", "999"]]
    for batch in [chunks, parts(other)]:
        store.upsert(
            EmbeddingResult(
                info=info, embeddings=[EmbeddedChunk(chunk=c, vector=[1.0, 0.0]) for c in batch]
            )
        )

    class Provider:
        def __init__(self):
            self.info = info

        def embed_query(self, query):
            return [1.0, 0.0]

    original_list = store.list_chunks

    def no_table_fetch(filters=None):
        assert filters is None or filters.table_id is None, "Search must not fetch connected rows"
        return original_list(filters)

    monkeypatch.setattr(store, "list_chunks", no_table_fetch)
    hits = search_documents(
        "Repeated",
        Provider(),
        store,
        top_k=1,
        filters=SearchFilters(discovery_id=document.source.discovery_id),
        options=options,
    )
    assert len(hits) == 1
    matched = hits[0].chunk
    assert matched in chunks
    assert matched.table_complete is False
    assert len(matched.table_rows) < len(document.tables[0].rows)
    assert matched.source_chunk_ids == []
    assert matched.source.discovery_id == document.source.discovery_id
    from app.api.workspace.sources import source_passage
    from app.tools.document_search import SearchTool

    evidence = SearchTool(Provider(), store, document.source.discovery_id).run(
        {"query": "Repeated", "top_k": 1}
    )
    assert len(evidence) == 1
    citation = source_passage(evidence[0])
    saved = next(c for c in chunks if str(c.chunk_id) == citation.chunk_id)
    assert citation.table_complete is False
    assert citation.table_id == saved.table_id
    assert citation.source_chunk_ids == []
    assert citation.text == saved.text
    assert json.loads(citation.text)["rows"] == saved.table_rows


def test_inconsistent_cells_and_cross_upload_parts_are_not_claimed_complete():
    chunks = parts(table_document())
    for change in ["cell", "upload", "page"]:
        bad = chunks[0].model_copy(deep=True)
        if change == "cell":
            bad.table_rows[0][0] = "Conflicting cell"
        elif change == "upload":
            bad.source.discovery_id = uuid4()
        else:
            bad.page_number = 2

        class Store:
            def list_chunks(self, filters):
                return chunks + [bad]

        assert expand_tables([SearchHit(chunk=chunks[0])], Store())[0].chunk.table_complete is False


def test_evidence_budget_reports_omitted_and_incomplete_tables():
    class Search:
        def run(self, arguments):
            return [
                {
                    "chunk_id": "large",
                    "table_id": "whole",
                    "table_complete": True,
                    "text": "x" * 1000,
                },
                {
                    "chunk_id": "small",
                    "table_id": "partial",
                    "table_complete": False,
                    "text": "Partial row",
                },
            ]

    state = ToolState(search_queries=["products"], max_evidence_chars=200)
    result = retrieve_evidence(state, {"search_documents": Search()})
    assert [item["chunk_id"] for item in result["evidence"]] == ["small"]
    selection = result["trace"][0]["selection"]
    assert selection["tables_omitted_by_budget"] == ["whole"]
    assert selection["incomplete_table_ids"] == ["partial"]


def test_legacy_chunk_json_still_loads_without_table_metadata():
    chunk = example().embeddings[0].chunk
    data = chunk.model_dump()
    for name in list(data):
        if name.startswith("table_") or name == "source_chunk_ids":
            del data[name]
    assert Chunk.model_validate(data).table_id is None


def test_qa_omits_oversized_table_before_answer_decision():
    from test_question_answer_graph import FakeModel

    from app.agents.qa.graph.workflow import answer_question

    class Search:
        def run(self, arguments):
            return [
                {
                    "chunk_id": "whole",
                    "table_id": "table",
                    "table_complete": True,
                    "text": "x" * 13000,
                }
            ]

    model = FakeModel(
        draft={"status": "not_found", "answer": "Not found in documents", "source_chunk_ids": []}
    )
    result = answer_question("List every product", model, {"search_documents": Search()})
    assert result.status == "not_found"
    assert len(model.requests) == 1
    assert result.trace[0]["selection"]["tables_omitted_by_budget"] == ["table"]
