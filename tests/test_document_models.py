"""Check the parsing output contract before implementing parsers."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.discovery import discover_bid_files
from app.schemas.content import TableBlock, TextBlock
from app.schemas.documents import ParsedDocument, ParsingIssue
from app.schemas.metadata import SourceMetadata


@pytest.fixture
def source(tmp_path: Path) -> SourceMetadata:
    (tmp_path / "original.pdf").touch()
    record = discover_bid_files(tmp_path)[0]
    return SourceMetadata(**record.model_dump())


def test_discovery_identity_and_unknown_metadata(source: SourceMetadata) -> None:
    assert source.folder_name == source.file_path.parent.name
    assert source.discovery_id.version == 4
    assert source.doc_type == "unknown"
    assert source.addendum_number is None
    assert source.document_date is None


def test_document_json_round_trip(source: SourceMetadata) -> None:
    document = ParsedDocument(
        source=source,
        page_count=2,
        text_blocks=[TextBlock(page_number=1, text="Delivery within 45 days.")],
        tables=[TableBlock(page_number=2, headers=["Product", "Qty"], rows=[["Laptop", "30"]])],
        issues=[ParsingIssue(code="review_required", message="Check the table.", page_number=2)],
    )
    restored = ParsedDocument.model_validate_json(document.model_dump_json())
    assert restored == document


@pytest.mark.parametrize("page", [0, -1])
def test_page_numbers_start_at_one(page: int) -> None:
    with pytest.raises(ValidationError):
        TextBlock(page_number=page, text="Some text")


def test_whitespace_only_text_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TextBlock(text=" \n ")


def test_table_preserves_empty_cells_and_optional_headers() -> None:
    table = TableBlock(rows=[["Laptop", None], ["Dock", "30"]])
    assert table.headers == []
    assert table.rows[0][1] is None


@pytest.mark.parametrize("rows", [[], [[]], [["Laptop", "30"], ["Dock"]]])
def test_invalid_table_rows_are_rejected(rows: list[list[str]]) -> None:
    with pytest.raises(ValidationError):
        TableBlock(rows=rows)


def test_pdf_requires_content_page_references(source: SourceMetadata) -> None:
    with pytest.raises(ValidationError, match="physical page number"):
        ParsedDocument(source=source, text_blocks=[TextBlock(text="Some text")])


def test_out_of_range_pages_are_rejected(source: SourceMetadata) -> None:
    with pytest.raises(ValidationError, match="exceeds"):
        ParsedDocument(
            source=source, page_count=1, text_blocks=[TextBlock(page_number=2, text="Text")]
        )


def test_html_uses_sections(source: SourceMetadata) -> None:
    html_source = SourceMetadata(**{**source.model_dump(), "file_type": "html"})
    document = ParsedDocument(
        source=html_source, text_blocks=[TextBlock(section="Dates", text="Closing date: June 10")]
    )
    assert document.text_blocks[0].page_number is None
    with pytest.raises(ValidationError, match="section references"):
        ParsedDocument(source=html_source, text_blocks=[TextBlock(page_number=1, text="Text")])


def test_failed_document_can_hold_only_an_issue(source: SourceMetadata) -> None:
    document = ParsedDocument(
        source=source,
        issues=[
            ParsingIssue(code="unreadable_file", message="Could not open file", severity="error")
        ],
    )
    assert document.text_blocks == []
    assert document.issues[0].page_number is None


def test_document_lists_are_independent(source: SourceMetadata) -> None:
    first = ParsedDocument(source=source)
    second = ParsedDocument(source=source)
    first.issues.append(ParsingIssue(code="empty_text", message="No text extracted"))
    assert second.issues == []
