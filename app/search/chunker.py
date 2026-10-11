"""Build source-preserving search chunks from prepared document content."""

import re
from uuid import uuid5

from app.ingestion.table_identity import assign_table_ids
from app.schemas.chunks import Chunk, ChunkedDocument, ChunkSettings
from app.schemas.prepared import PreparedDocument
from app.search.table_chunks import chunk_tables
from app.search.text_splitter import split_text


def chunk_document(
    document: PreparedDocument, settings: ChunkSettings | None = None
) -> ChunkedDocument:
    """Keep existing text chunks and add whole-row chunks for detected tables."""
    settings = settings or ChunkSettings()
    document = document.model_copy(deep=True)
    assign_table_ids(document)
    chunks = []
    for index, block in enumerate(document.text_blocks):
        ranges = [(0, len(block.text))]
        if settings.structure_aware and document.source.doc_type == "addendum":
            starts = [match.start() for match in re.finditer(r"(?m)^\d+\.\s+", block.text)]
            boundaries = sorted(set([0, *starts, len(block.text)]))
            ranges = list(zip(boundaries, boundaries[1:]))
        spans = []
        for start, end in ranges:
            for span in split_text(block.text[start:end], settings):
                spans.append((start + span.start, start + span.end, span.text))
        for start, end, text in spans:
            identity = (
                f"{document.source.relative_path.as_posix()}|native|text|{index}|"
                f"{start}|{end}|{text}"
            )
            chunks.append(
                Chunk(
                    chunk_id=uuid5(document.source.discovery_id, identity),
                    source=document.source.model_copy(deep=True),
                    page_number=block.page_number,
                    section=block.section,
                    heading=block.heading,
                    block_index=index,
                    start_char=start,
                    end_char=end,
                    text=text,
                )
            )
    chunks.extend(chunk_tables(document, settings))
    return ChunkedDocument(
        document=document.model_copy(deep=True),
        settings=settings.model_copy(deep=True),
        chunks=chunks,
    )


def chunk_documents(
    documents: list[PreparedDocument], settings: ChunkSettings | None = None
) -> list[ChunkedDocument]:
    return [chunk_document(document, settings) for document in documents]
