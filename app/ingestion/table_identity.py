"""Assign upload-scoped identities without guessing relationships between pages."""

from uuid import uuid5


def assign_table_ids(document) -> None:
    for index, table in enumerate(document.tables):
        identity = (
            f"{document.source.relative_path.as_posix()}|table|"
            f"{table.page_number}|{table.section}|{index}"
        )
        table.table_id = uuid5(document.source.discovery_id, identity)
