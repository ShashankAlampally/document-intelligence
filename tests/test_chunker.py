"""Check chunk provenance, baseline evidence retention, and run-scoped identities."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.chunks import ChunkedDocument, ChunkSettings
from app.schemas.content import ImageRegion, TableBlock, TextBlock
from app.schemas.documents import ParsingIssue
from app.schemas.metadata import SourceMetadata
from app.schemas.prepared import PreparedDocument
from app.search.chunker import chunk_document, chunk_documents


def make_document(file_type: str = "pdf") -> PreparedDocument:
    location = {"page_number": 1} if file_type == "pdf" else {"section": "section-2"}
    second_location = {"page_number": 2} if file_type == "pdf" else {"section": "section-3"}
    return PreparedDocument(
        source=SourceMetadata(
            discovery_id=uuid4(),
            folder_name="Example",
            file_name=f"bid.{file_type}",
            relative_path=Path(f"bid.{file_type}"),
            file_path=Path(f"/example/bid.{file_type}"),
            file_type=file_type,
        ),
        page_count=2 if file_type == "pdf" else None,
        text_blocks=[
            TextBlock(**location, heading="Delivery", text="Delivery within 45 days. " * 8),
            TextBlock(**second_location, text="Warranty lasts three years."),
        ],
        tables=[TableBlock(**location, rows=[["Unique table value", "30"]])],
        images=[ImageRegion(page_number=1, name="logo", bbox=(0, 0, 10, 10))]
        if file_type == "pdf"
        else [],
        issues=[ParsingIssue(code="review_required", message="Retain this warning")],
    )


@pytest.mark.parametrize("file_type", ["pdf", "html"])
def test_source_boundaries_offsets_and_retained_evidence(file_type: str) -> None:
    original = make_document(file_type)
    result = chunk_document(original, ChunkSettings(max_chars=70, overlap_chars=10))
    assert len(result.chunks) > len(original.text_blocks)
    for chunk in result.chunks:
        if chunk.content_type == "table":
            continue
        block = original.text_blocks[chunk.block_index]
        assert chunk.source == original.source
        assert chunk.page_number == block.page_number
        assert chunk.section == block.section
        assert chunk.heading == block.heading
        assert chunk.text == block.text[chunk.start_char : chunk.end_char]
        assert chunk.content_type == "text"
        assert chunk.extraction_method == "native"
        assert "Unique table value" not in chunk.text
    assert result.document.tables[0].rows == original.tables[0].rows
    assert result.document.tables[0].table_id is not None
    assert original.tables[0].table_id is None
    assert any(chunk.content_type == "table" for chunk in result.chunks)
    assert result.document.images == original.images
    assert result.document.issues == original.issues
    assert ChunkedDocument.model_validate_json(result.model_dump_json()) == result


def test_chunk_ids_repeat_within_run_and_change_for_new_discovery() -> None:
    original = make_document()
    first = chunk_document(original)
    assert [c.chunk_id for c in first.chunks] == [
        c.chunk_id for c in chunk_document(original).chunks
    ]
    assert len({c.chunk_id for c in first.chunks}) == len(first.chunks)
    new_run = original.model_copy(deep=True)
    new_run.source.discovery_id = uuid4()
    assert first.chunks[0].chunk_id != chunk_document(new_run).chunks[0].chunk_id


def test_result_is_independent_of_input() -> None:
    original = make_document()
    before = original.model_dump_json()
    result = chunk_document(original)
    result.chunks[0].source.folder_name = "Changed"
    result.document.tables[0].rows[0][0] = "Changed"
    assert original.model_dump_json() == before


def test_failed_document_is_retained_without_chunks() -> None:
    original = make_document()
    original.text_blocks = []
    original.tables = []
    original.issues = [
        ParsingIssue(code="unreadable_file", message="Cannot open", severity="error")
    ]
    result = chunk_documents([original])[0]
    assert result.chunks == []
    assert result.document.issues == original.issues
    assert chunk_documents([]) == []


def test_structure_aware_addendum_keeps_question_answer_pairs_and_offsets():
    doc = make_document()
    doc.source.doc_type = "addendum"
    text = (
        "ADDENDUM\n1. Which devices?\nAnswer: Laptops only.\n"
        "2. Which enrollment?\nAnswer: Google Management."
    )
    doc.text_blocks = [TextBlock(page_number=1, text=text)]
    doc.tables = []
    result = chunk_document(
        doc, ChunkSettings(max_chars=60, overlap_chars=10, structure_aware=True)
    )
    pairs = [c for c in result.chunks if c.text.startswith(("1.", "2."))]
    assert len(result.chunks) == 3
    assert len(pairs) == 2
    assert all("Answer:" in c.text for c in pairs)
    assert all(text[c.start_char : c.end_char] == c.text for c in result.chunks)


def test_structure_aware_tables_retain_headers_cells_and_row_provenance():
    doc = make_document()
    doc.tables[0].headers = ["Model", "Quantity"]
    doc.tables[0].rows = [["Dell\\nLatitude 5550", "30"]]
    result = chunk_document(doc, ChunkSettings(structure_aware=True))
    table = next(c for c in result.chunks if c.content_type == "table")
    assert "Model | Quantity" in table.text
    assert "Dell\nLatitude 5550 | 30" in table.text
    assert table.table_rows == doc.tables[0].rows
    assert table.table_headers == doc.tables[0].headers
    assert table.table_row_start == table.table_row_end == 1


def test_snapshot_regroup_preserves_content_and_isolates_discovery():
    from scripts.index_retrieval_variant import regroup

    doc = make_document()
    doc.source.doc_type = "addendum"
    doc.text_blocks = [
        TextBlock(
            page_number=1,
            text="1. Need etching?\nAnswer: Laptops only.\n2. Need tags?\nAnswer: Yes.",
        )
    ]
    original = chunk_document(doc, ChunkSettings(max_chars=50, overlap_chars=10)).chunks
    before = [c.model_dump_json() for c in original]
    new_id = uuid4()
    changed = regroup(original, new_id)
    assert [c.model_dump_json() for c in original] == before
    assert all(c.source.discovery_id == new_id for c in changed)
    assert any("1. Need etching?\nAnswer: Laptops only." == c.text for c in changed)
    assert any("2. Need tags?\nAnswer: Yes." == c.text for c in changed)
    table = next(c for c in changed if c.content_type == "table")
    assert table.table_rows == doc.tables[0].rows
    assert "Unique table value" in table.text
