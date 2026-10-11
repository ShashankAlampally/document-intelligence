"""Refresh labels on one Chroma upload without changing embeddings or chunk IDs."""

from uuid import UUID

from app.ingestion.document_metadata import classify_source
from app.schemas.chunks import Chunk
from app.search.store_metadata import chunk_metadata


def _chunk_order(chunk: Chunk) -> tuple:
    return (chunk.page_number or 0, chunk.block_index, chunk.start_char)


def refresh_metadata(store, discovery_id: UUID) -> int:
    records = store.collection.get(where={"discovery_id": str(discovery_id)}, include=["metadatas"])
    if not records["ids"]:
        raise ValueError("No chunks found for this discovery ID")
    chunks = [Chunk.model_validate_json(item["chunk_json"]) for item in records["metadatas"]]
    opening_text = {}
    for chunk in sorted(chunks, key=_chunk_order):
        opening_text.setdefault(chunk.source.relative_path, chunk.text)
    ids = []
    metadatas = []
    for record_id, old_metadata, chunk in zip(records["ids"], records["metadatas"], chunks):
        source = classify_source(chunk.source, opening_text[chunk.source.relative_path])
        updated = chunk.model_copy(update={"source": source})
        metadata = {**old_metadata, **chunk_metadata(updated)}
        if metadata != old_metadata:
            ids.append(record_id)
            metadatas.append(metadata)
    batch_size = store.client.get_max_batch_size()
    for start in range(0, len(ids), batch_size):
        store.collection.update(
            ids=ids[start : start + batch_size], metadatas=metadatas[start : start + batch_size]
        )
    return len(ids)
