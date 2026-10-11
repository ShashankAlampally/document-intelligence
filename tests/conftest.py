"""Generate small PDFs with known content for extraction tests."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from app.ingestion.discovery import discover_bid_files
from app.schemas.files import FileRecord


@pytest.fixture
def sample_pdf(tmp_path: Path) -> FileRecord:
    """Three pages: text+image, ruled table, then image-only."""
    path = tmp_path / "sample.pdf"
    image = Image.new("RGB", (320, 100), "white")
    ImageDraw.Draw(image).text((10, 20), "Words inside image only", fill="black")
    stream = BytesIO()
    image.save(stream, format="PNG")
    reader = ImageReader(stream)

    canvas = Canvas(str(path), pagesize=(612, 792))
    canvas.drawString(50, 740, "Delivery within 45 days of award.")
    canvas.drawImage(reader, 50, 550, width=320, height=100)
    canvas.showPage()

    table = Table(
        [["Product", "Quantity"], ["Laptop", "30"], ["Dock", "30"]],
        colWidths=[180, 100],
        rowHeights=30,
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, "black")]))
    table.wrapOn(canvas, 280, 90)
    table.drawOn(canvas, 50, 600)
    canvas.showPage()

    canvas.drawImage(reader, 50, 550, width=320, height=100)
    canvas.showPage()
    canvas.save()
    return discover_bid_files(tmp_path)[0]


@pytest.fixture
def borderless_pdf(tmp_path: Path) -> FileRecord:
    path = tmp_path / "borderless.pdf"
    canvas = Canvas(str(path))
    for index, (description, sku) in enumerate(
        [
            ("Description", "SKU"),
            ("Laptop base", "210-ABCD"),
            ("Memory module", "370-EFGH"),
            ("Storage drive", "400-IJKL"),
        ]
    ):
        canvas.drawString(50, 740 - index * 30, description)
        canvas.drawString(300, 740 - index * 30, sku)
    canvas.showPage()
    canvas.save()
    return discover_bid_files(tmp_path)[0]
