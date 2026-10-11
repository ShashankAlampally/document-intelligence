"""Whole-row chunks with explicit table provenance and lossless cell serialization."""

import json
from uuid import uuid5

from app.schemas.chunks import Chunk
from app.search.evidence_text import readable_table


def table_text(headers, rows) -> str:
    # JSON preserves null/merged cells, embedded newlines and column boundaries.
    return json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False)


def row_chunk(template: Chunk, rows: list, start: int) -> Chunk:
    render = table_text if template.text.lstrip().startswith("{") else readable_table
    text = render(template.table_headers, rows)
    end = start + len(rows) - 1
    return template.model_copy(
        deep=True,
        update={
            "chunk_id": uuid5(template.table_id, f"rows|{start}|{end}|{text}"),
            "text": text,
            "start_char": 0,
            "end_char": len(text),
            "table_row_start": start,
            "table_row_end": end,
            "table_rows": rows,
            "table_complete": False,
            "source_chunk_ids": [],
        },
    )


def chunk_tables(document, settings) -> list[Chunk]:
    chunks = []
    render = readable_table if settings.structure_aware else table_text
    for index, table in enumerate(document.tables):
        text = render(table.headers, table.rows)
        template = Chunk(
            chunk_id=table.table_id,
            table_id=table.table_id,
            source=document.source.model_copy(deep=True),
            content_type="table",
            page_number=table.page_number,
            section=table.section,
            heading=table.caption,
            block_index=index,
            start_char=0,
            end_char=len(text),
            text=text,
            table_row_start=1,
            table_row_end=len(table.rows),
            table_total_rows=len(table.rows),
            table_headers=table.headers,
            table_rows=table.rows,
            table_complete=False,
        )
        rows = []
        start = 1
        for row in table.rows:
            if rows and len(render(table.headers, rows + [row])) > settings.max_chars:
                chunks.append(row_chunk(template, rows, start))
                start += len(rows)
                rows = []
            rows.append(row)
        if rows:
            chunks.append(row_chunk(template, rows, start))
    return chunks
