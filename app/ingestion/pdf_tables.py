"""Extract ruled tables, with a conservative aligned-text fallback."""

from pymupdf import Page

from app.ingestion.pdf_borderless import extract_borderless_rows
from app.schemas.content import TableBlock


def _normalize_rows(raw_rows: list[list[str | None]]) -> list[list[str | None]]:
    rows = [
        [cell.strip() or None if cell is not None else None for cell in row] for row in raw_rows
    ]
    rows = [row for row in rows if any(cell is not None for cell in row)]
    width = max((len(row) for row in rows), default=0)
    return [row + [None] * (width - len(row)) for row in rows]


def extract_pdf_tables(page: Page, page_number: int) -> list[TableBlock]:
    detected = page.find_tables().tables
    if not detected:
        rows = extract_borderless_rows(page)
        return [TableBlock(page_number=page_number, rows=rows)] if rows else []

    tables = []
    for table in detected:
        rows = _normalize_rows(table.extract())
        if not rows or len(rows[0]) < 2:
            continue
        # Keep the first row as data: not every table has a header row.
        tables.append(TableBlock(page_number=page_number, rows=rows))
    return tables
