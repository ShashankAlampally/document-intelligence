"""Reindex grouping from an immutable saved corpus, reusing unchanged vectors."""

import argparse
import json
from collections import Counter, defaultdict
from uuid import UUID, uuid4, uuid5

from app.api.workspace.files import save_json
from app.config import Settings
from app.schemas.chunks import ChunkSettings
from app.schemas.content import TextBlock
from app.schemas.embeddings import EmbeddedChunk, EmbeddingResult
from app.schemas.prepared import PreparedDocument
from app.schemas.search import FileIndexReport, IndexReport, SearchFilters
from app.search.chroma_store import ChromaVectorStore
from app.search.chunker import chunk_document
from app.search.embeddings import embed_chunks
from app.search.evidence_text import cell_text, evidence_text
from app.search.local_embeddings import LocalEmbeddingProvider
from app.search.store_metadata import filter_metadata


def regroup(chunks, new_id):
    changed = []
    groups = defaultdict(list)
    settings = ChunkSettings(max_chars=1000, overlap_chars=100, structure_aware=True)
    for chunk in chunks:
        if chunk.content_type == "text" and chunk.source.doc_type == "addendum":
            key = (chunk.source.relative_path, chunk.page_number, chunk.section, chunk.block_index)
            groups[key].append(chunk)
            continue
        clone = chunk.model_copy(deep=True)
        clone.source.discovery_id = new_id
        if clone.content_type == "table":
            clone.text = cell_text(evidence_text(clone.text))
            clone.start_char = 0
            clone.end_char = len(clone.text)
        clone.chunk_id = uuid5(new_id, str(chunk.chunk_id) + clone.text)
        changed.append(clone)
    for key, group in groups.items():
        end = max(c.end_char for c in group)
        chars = [None] * end
        for c in group:
            for i, char in enumerate(c.text, c.start_char):
                if chars[i] is not None and chars[i] != char:
                    raise ValueError(f"Conflicting source offsets: {key}")
                chars[i] = char
        if any(char is None for char in chars):
            raise ValueError(f"Incomplete source block: {key}; cannot regroup safely")
        template = group[0]
        source = template.source.model_copy(update={"discovery_id": new_id}, deep=True)
        block = TextBlock(
            page_number=template.page_number,
            section=template.section,
            heading=template.heading,
            text="".join(chars),
        )
        doc = PreparedDocument(source=source, text_blocks=[block])
        for c in chunk_document(doc, settings).chunks:
            c.block_index = template.block_index
            c.chunk_id = uuid5(new_id, f"{key}|{c.start_char}|{c.end_char}|{c.text}")
            changed.append(c)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-id", type=UUID, required=True)
    args = parser.parse_args()
    config = Settings()
    store = ChromaVectorStore(config.vector_db_dir, config.vector_collection)
    filters = SearchFilters(discovery_id=args.from_id)
    chunks = store.list_chunks(filters)
    if not chunks:
        parser.error("Source index has no chunks")
    new_id = uuid4()
    variant = regroup(chunks, new_id)
    saved = store.collection.get(where=filter_metadata(filters), include=["embeddings"])
    old_by_id = {str(c.chunk_id): c for c in chunks}
    cache = {
        old_by_id[id].text: vector.tolist() for id, vector in zip(saved["ids"], saved["embeddings"])
    }
    cached = [EmbeddedChunk(chunk=c, vector=cache[c.text]) for c in variant if c.text in cache]
    pending = [c for c in variant if c.text not in cache]
    print(
        f"{chunks[0].source.folder_name}: reusing {len(cached)} vectors; "
        f"encoding {len(pending)} changed chunks",
        flush=True,
    )
    provider = LocalEmbeddingProvider(config)
    fresh = embed_chunks(pending, provider)
    result = EmbeddingResult(info=fresh.info, embeddings=cached + fresh.embeddings)
    stored = store.upsert(result)
    counts = Counter(r.chunk.source.relative_path for r in result.embeddings)
    report = IndexReport(
        discovery_id=new_id,
        folder_name=chunks[0].source.folder_name,
        model=fresh.info,
        chunk_settings=ChunkSettings(max_chars=1000, overlap_chars=100, structure_aware=True),
        stored_chunks=stored,
        collection_count=store.count(),
        files=[FileIndexReport(relative_path=p, chunk_count=n) for p, n in counts.items()],
    )
    directory = config.vector_db_dir.parent / "manifests"
    save_json(directory / f"{new_id}.json", report.model_dump_json(indent=2))
    save_json(
        directory / f"{new_id}.variant.json",
        json.dumps(
            {
                "source_discovery_id": str(args.from_id),
                "discovery_id": str(new_id),
                "reused_vectors": len(cached),
                "changed_chunks": len(pending),
                "method": "Fixed source snapshot; regroup addendum blocks and decode table text. "
                "No reparsing, source additions, query gold or LLM calls.",
            },
            indent=2,
        ),
    )
    print(f"Discovery ID: {new_id}; stored chunks: {stored}", flush=True)


if __name__ == "__main__":
    main()
