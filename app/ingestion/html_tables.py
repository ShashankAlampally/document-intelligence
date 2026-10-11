"""Normalize HTML tables without guessing headers or merged-cell meaning."""

from bs4 import Tag

from app.schemas.content import TableBlock


def extract_html_table(table: Tag, section: str) -> TableBlock | None:
    """Keep merged-cell text once; covered cells are None, as in PDF tables."""
    if table.find("table"):
        raise ValueError("Nested table layout requires review; text is retained")
    grid: dict[tuple[int, int], str | None] = {}
    row_count = 0
    for number, row in enumerate(table.find_all("tr")):
        row_count = number + 1
        column = 0
        for cell in row.find_all(["td", "th"], recursive=False):
            while (number, column) in grid:
                column += 1
            height = int(cell.get("rowspan", 1))
            width = int(cell.get("colspan", 1))
            if not 1 <= height <= 100 or not 1 <= width <= 100:
                raise ValueError("Unsupported table span; text is retained")
            text = " ".join(cell.stripped_strings) or None
            for down in range(height):
                for across in range(width):
                    position = (number + down, column + across)
                    if position in grid:
                        raise ValueError("Overlapping table spans; text is retained")
                    grid[position] = text if down == across == 0 else None
            column += width
    if not grid:
        return None
    if max(row for row, _ in grid) >= row_count:
        raise ValueError("Rowspan exceeds table rows; text is retained")
    columns = max(column for _, column in grid) + 1
    rows = [[grid.get((row, column)) for column in range(columns)] for row in range(row_count)]
    caption = table.find("caption", recursive=False)
    return TableBlock(
        section=section,
        rows=rows,
        caption=caption.get_text(" ", strip=True) if caption else None,
    )
