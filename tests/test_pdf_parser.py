"""Verify actual PDF extraction and recovery from individual failures."""

from pathlib import Path

import pytest
from pymupdf import Page

from app.ingestion import pdf_parser
from app.ingestion.discovery import discover_bid_files
from app.schemas.documents import ParsedDocument
from app.schemas.files import FileRecord


def test_text_and_source_references(sample_pdf: FileRecord) -> None:
    result = pdf_parser.parse_pdf(sample_pdf)
    assert result.page_count == 3
    assert result.source.discovery_id == sample_pdf.discovery_id
    assert result.source.folder_name == sample_pdf.folder_name
    assert result.source.doc_type == "unknown"
    assert "Delivery within 45 days" in result.text_blocks[0].text
    assert result.text_blocks[0].page_number == 1
    assert all("Words inside image" not in block.text for block in result.text_blocks)
    assert ParsedDocument.model_validate_json(result.model_dump_json()) == result


def test_ruled_table_preserves_rows(sample_pdf: FileRecord) -> None:
    result = pdf_parser.parse_pdf(sample_pdf)
    table = next(table for table in result.tables if table.page_number == 2)
    assert table.headers == []
    assert table.rows == [["Product", "Quantity"], ["Laptop", "30"], ["Dock", "30"]]


def test_borderless_table_keeps_description_with_sku(borderless_pdf: FileRecord) -> None:
    result = pdf_parser.parse_pdf(borderless_pdf)
    assert result.tables
    rows = result.tables[0].rows
    assert any(
        "210-ABCD" in row and "Laptop base" in " ".join(cell or "" for cell in row) for row in rows
    )


def test_mixed_and_image_only_pages(sample_pdf: FileRecord) -> None:
    result = pdf_parser.parse_pdf(sample_pdf)
    assert [image.page_number for image in result.images] == [1, 3]
    assert result.images[0].bbox == pytest.approx((50, 142, 370, 242))
    assert any(block.page_number == 1 for block in result.text_blocks)
    assert not any(issue.page_number == 1 for issue in result.issues)
    assert any(
        issue.code == "no_text_extracted" and issue.page_number == 3 for issue in result.issues
    )


def test_blank_page_is_flagged(tmp_path: Path) -> None:
    from reportlab.pdfgen.canvas import Canvas

    canvas = Canvas(str(tmp_path / "blank.pdf"))
    canvas.showPage()
    canvas.save()
    result = pdf_parser.parse_pdf(discover_bid_files(tmp_path)[0])
    assert result.text_blocks == []
    assert result.images == []
    assert result.issues[0].code == "no_text_extracted"


def test_unreadable_pdf_returns_error(tmp_path: Path) -> None:
    (tmp_path / "broken.pdf").write_text("not a PDF")
    result = pdf_parser.parse_pdf(discover_bid_files(tmp_path)[0])
    assert result.page_count is None
    assert result.issues[0].code == "unreadable_file"
    assert result.issues[0].severity == "error"


def test_non_pdf_record_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "page.html").touch()
    with pytest.raises(ValueError, match="PDF file record"):
        pdf_parser.parse_pdf(discover_bid_files(tmp_path)[0])


def test_table_failure_preserves_text_and_images(
    sample_pdf: FileRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object) -> None:
        raise RuntimeError("table failure")

    monkeypatch.setattr(pdf_parser, "extract_pdf_tables", fail)
    result = pdf_parser.parse_pdf(sample_pdf)
    assert result.text_blocks and result.images
    assert sum(issue.code == "table_extraction_failed" for issue in result.issues) == 3


def test_text_failure_does_not_stop_later_pages(
    sample_pdf: FileRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Page.get_text

    def extract(page: Page, *args: object, **kwargs: object) -> str:
        if page.number == 0 and args and args[0] == "text":
            raise RuntimeError("text failure")
        return original(page, *args, **kwargs)

    monkeypatch.setattr(Page, "get_text", extract)
    result = pdf_parser.parse_pdf(sample_pdf)
    assert any(
        issue.code == "text_extraction_failed" and issue.page_number == 1 for issue in result.issues
    )
    assert any(block.page_number == 2 for block in result.text_blocks)
    assert any(table.page_number == 2 for table in result.tables)
    assert [image.page_number for image in result.images] == [1, 3]
