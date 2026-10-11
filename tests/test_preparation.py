"""Verify whitespace cleanup preserves meaning, table shape, and provenance."""

from pathlib import Path

import pytest

from app.ingestion.cleaner import clean_text
from app.ingestion.discovery import discover_bid_files
from app.ingestion.preparation import prepare_document, prepare_documents
from app.schemas.content import ImageRegion, TableBlock, TextBlock
from app.schemas.documents import ParsedDocument, ParsingIssue
from app.schemas.metadata import SourceMetadata
from app.schemas.prepared import PreparedDocument


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Delivery   within\t45 days.", "Delivery within 45 days."),
        ("  First\r\n Second\rThird  ", "First\nSecond\nThird"),
        ("First\n \n\n\nSecond", "First\n\nSecond"),
        ("Price\u00a0 £30; Qty: 30; 06/10/2024", "Price £30; Qty: 30; 06/10/2024"),
        ("thawkins@treasurer.state.md\n.us", "thawkins@treasurer.state.md\n.us"),
        (" \t\r\n ", ""),
    ],
)
def test_conservative_cleanup(original: str, expected: str) -> None:
    assert clean_text(original) == expected
    assert clean_text(expected) == expected


def make_document(tmp_path: Path, file_type: str = "pdf") -> ParsedDocument:
    (tmp_path / f"bid.{file_type}").touch()
    record = discover_bid_files(tmp_path)[0]
    location = {"page_number": 1} if file_type == "pdf" else {"section": "section-2"}
    return ParsedDocument(
        source=SourceMetadata(**record.model_dump()),
        page_count=1 if file_type == "pdf" else None,
        text_blocks=[
            TextBlock(**location, text="Delivery   within 45 days.\nPage 1", heading=" Terms  ")
        ],
        tables=[
            TableBlock(
                **location,
                headers=[" Product ", " Qty "],
                caption=" Devices  ",
                rows=[["Dell  Laptop", "30"], [None, " \t "], [None, None]],
            )
        ],
        images=[ImageRegion(page_number=1, name="logo", bbox=(0, 0, 10, 10))]
        if file_type == "pdf"
        else [],
        issues=[ParsingIssue(code="review_required", message="Keep this warning")],
    )


@pytest.mark.parametrize("file_type", ["pdf", "html"])
def test_preparation_preserves_locations_and_table_shape(tmp_path: Path, file_type: str) -> None:
    original = make_document(tmp_path, file_type)
    prepared = prepare_document(original)
    assert prepared.source == original.source
    assert prepared.page_count == original.page_count
    assert prepared.images == original.images
    assert prepared.issues == original.issues
    assert prepared.text_blocks[0].text == "Delivery within 45 days.\nPage 1"
    assert prepared.text_blocks[0].heading == "Terms"
    assert prepared.text_blocks[0].page_number == original.text_blocks[0].page_number
    assert prepared.text_blocks[0].section == original.text_blocks[0].section
    assert prepared.tables[0].rows == [["Dell Laptop", "30"], [None, None], [None, None]]
    assert prepared.tables[0].headers == ["Product", "Qty"]
    assert prepared.tables[0].caption == "Devices"
    assert PreparedDocument.model_validate_json(prepared.model_dump_json()) == prepared


def test_prepared_data_is_independent_of_original(tmp_path: Path) -> None:
    original = make_document(tmp_path)
    before = original.model_dump_json()
    prepared = prepare_document(original)
    prepared.source.folder_name = "Changed copy"
    prepared.tables[0].rows[0][0] = "Changed product"
    prepared.images[0].name = "Changed image"
    prepared.issues[0].message = "Changed issue"
    assert original.model_dump_json() == before


def test_failed_documents_and_empty_list_are_retained(tmp_path: Path) -> None:
    original = make_document(tmp_path)
    failed = ParsedDocument(
        source=original.source,
        issues=[ParsingIssue(code="unreadable_file", message="Cannot open", severity="error")],
    )
    results = prepare_documents([original, failed])
    assert len(results) == 2
    assert results[1].issues == failed.issues
    assert results[1].text_blocks == []
    assert prepare_documents([]) == []


def test_preparation_is_idempotent(tmp_path: Path) -> None:
    prepared = prepare_document(make_document(tmp_path))
    assert prepare_document(prepared) == prepared
