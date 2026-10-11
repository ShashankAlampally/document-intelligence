"""Reconstruct a detected table from its stored rows, keeping real chunk provenance."""

from uuid import uuid5

from app.schemas.search import SearchFilters
from app.search.table_chunks import table_text


def expand_tables(hits, store, filters=None):
    expanded = []
    seen = set()
    for hit in hits:
        seed = hit.chunk
        if seed.table_id is None:
            expanded.append(hit)
            continue
        if seed.table_id in seen:
            continue
        scoped = (filters or SearchFilters()).model_copy(
            update={
                "discovery_id": seed.source.discovery_id,
                "file_name": seed.source.file_name,
                "table_id": seed.table_id,
            }
        )
        parts = store.list_chunks(scoped)
        rows = {}
        consistent = True
        for part in parts:
            if (
                part.table_id != seed.table_id
                or part.source.discovery_id != seed.source.discovery_id
                or part.source.relative_path != seed.source.relative_path
                or part.page_number != seed.page_number
                or part.section != seed.section
                or part.table_total_rows != seed.table_total_rows
                or part.table_headers != seed.table_headers
            ):
                consistent = False
                break
            for index, row in enumerate(part.table_rows, start=part.table_row_start):
                if index in rows and rows[index] != row:
                    consistent = False
                rows[index] = row
        if not consistent or set(rows) != set(range(1, seed.table_total_rows + 1)):
            expanded.append(
                hit.model_copy(update={"chunk": seed.model_copy(update={"table_complete": False})})
            )
            continue
        seen.add(seed.table_id)
        ordered = [rows[index] for index in range(1, seed.table_total_rows + 1)]
        text = table_text(seed.table_headers, ordered)
        complete = seed.model_copy(
            deep=True,
            update={
                "chunk_id": uuid5(seed.table_id, "assembled-table"),
                "text": text,
                "start_char": 0,
                "end_char": len(text),
                "table_rows": ordered,
                "table_row_start": 1,
                "table_row_end": len(ordered),
                "table_complete": True,
                "source_chunk_ids": sorted({part.chunk_id for part in parts}, key=str),
            },
        )
        expanded.append(hit.model_copy(update={"chunk": complete}))
    return expanded
