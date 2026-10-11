"""Readable table cells for retrieval; structured row metadata remains intact."""

import json


def cell_text(value):
    return str(value).replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")


def readable_table(headers, rows):
    lines = []
    if any(headers):
        lines.append(" | ".join(cell_text(cell) if cell is not None else "" for cell in headers))
    for row in rows:
        cells = [cell_text(cell) for cell in row if cell is not None and str(cell).strip()]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def evidence_text(text):
    """Decode only recognized table JSON; never unescape arbitrary document text."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return text
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return text
    rows = data["rows"]
    headers = data.get("headers", [])
    if not isinstance(headers, list) or not all(isinstance(row, list) for row in rows):
        return text
    if any(cell is not None and not isinstance(cell, str) for row in rows for cell in row):
        return text
    return readable_table(headers, rows)
