"""Regression checks for the aligned-column fallback."""

from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from app.ingestion.discovery import discover_bid_files
from app.ingestion.pdf_parser import parse_pdf


def test_long_description_and_final_continuation(tmp_path: Path) -> None:
    canvas = Canvas(str(tmp_path / "columns.pdf"))
    canvas.setFont("Helvetica", 10)
    rows = [
        ("Description", "SKU"),
        ("Laptop base", "AAA-001"),
        ("Memory", "BBB-002"),
        ("A longer description ending near the code", "CCC-003"),
    ]
    for index, (description, sku) in enumerate(rows):
        canvas.drawString(50, 740 - index * 30, description)
        canvas.drawRightString(300, 740 - index * 30, sku)
    canvas.drawString(50, 638, "continued description")
    canvas.showPage()
    canvas.save()

    result = parse_pdf(discover_bid_files(tmp_path)[0])
    rows = result.tables[0].rows
    assert len(rows) == 4
    assert rows[-1][1] == "CCC-003"
    assert "continued description" in rows[-1][0]


def test_paragraphs_are_not_split_into_tables(tmp_path: Path) -> None:
    canvas = Canvas(str(tmp_path / "prose.pdf"))
    for index in range(5):
        canvas.drawString(
            50, 740 - index * 20, "This is an ordinary sentence about delivery requirements."
        )
    canvas.showPage()
    canvas.save()

    result = parse_pdf(discover_bid_files(tmp_path)[0])
    assert result.text_blocks
    assert result.tables == []
