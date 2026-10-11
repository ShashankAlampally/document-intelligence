"""Encode filterable metadata and preserve complete chunk provenance."""

from app.schemas.chunks import Chunk
from app.schemas.embeddings import EmbeddingInfo
from app.schemas.search import SearchFilters


def chunk_metadata(chunk: Chunk) -> dict:
    source = chunk.source
    values = {
        "folder_name": source.folder_name,
        "discovery_id": str(source.discovery_id),
        "file_name": source.file_name,
        "relative_path": source.relative_path.as_posix(),
        "doc_type": source.doc_type,
        "addendum_number": source.addendum_number,
        "document_date": source.document_date.isoformat() if source.document_date else None,
        "page_number": chunk.page_number,
        "section": chunk.section,
        "content_type": chunk.content_type,
        "extraction_method": chunk.extraction_method,
        "table_id": str(chunk.table_id) if chunk.table_id else None,
        "chunk_json": chunk.model_dump_json(),
    }
    return {key: value for key, value in values.items() if value is not None}


def filter_metadata(filters: SearchFilters | None) -> dict | None:
    if filters is None:
        return None
    values = filters.model_dump(mode="json")
    clauses = [{key: value} for key, value in values.items() if value is not None]
    return {"$and": clauses} if len(clauses) > 1 else clauses[0] if clauses else None


def check_model(stored: EmbeddingInfo, incoming: EmbeddingInfo) -> None:
    # Library patch versions can differ; model space and preprocessing cannot.
    if stored.model_dump(exclude={"library_version"}) != incoming.model_dump(
        exclude={"library_version"}
    ):
        raise ValueError(
            "Embedding model/configuration differs from this collection; use a new collection"
        )
