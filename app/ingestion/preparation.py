"""Prepare parsed documents in memory, preserving originals and source locations."""

from app.ingestion.cleaner import clean_optional_text, clean_text
from app.schemas.content import TableBlock, TextBlock
from app.schemas.documents import ParsedDocument
from app.schemas.prepared import PreparedDocument


def _prepare_table(table: TableBlock) -> TableBlock:
    data = table.model_dump()
    data["headers"] = [clean_optional_text(cell) for cell in table.headers]
    data["rows"] = [[clean_optional_text(cell) for cell in row] for row in table.rows]
    data["caption"] = clean_optional_text(table.caption)
    # Keep every row and column, including empty/merged-cell placeholders.
    return TableBlock(**data)


def prepare_document(document: ParsedDocument) -> PreparedDocument:
    """Clean text and table cells while retaining metadata, images, and issues.

    model_dump creates independent data before validation into the prepared model.
    Preparation does not fix table alignment or remove duplicated table text.
    """
    data = document.model_dump()
    blocks = []
    for block in document.text_blocks:
        text = clean_text(block.text)
        if text:
            block_data = block.model_dump()
            block_data.update(text=text, heading=clean_optional_text(block.heading))
            blocks.append(TextBlock(**block_data))
    data["text_blocks"] = blocks
    data["tables"] = [_prepare_table(table) for table in document.tables]
    return PreparedDocument(**data)


def prepare_documents(documents: list[ParsedDocument]) -> list[PreparedDocument]:
    """Prepare a pipeline result without parsing files again or writing outputs."""
    return [prepare_document(document) for document in documents]
