"""Index one folder without reparsing or re-embedding other stored uploads."""

from collections import Counter
from pathlib import Path
from time import perf_counter

from app.ingestion.pipeline import parse_folder
from app.ingestion.preparation import prepare_documents
from app.schemas.chunks import ChunkSettings
from app.schemas.search import FileIndexReport, IndexReport
from app.search.chunker import chunk_documents
from app.search.embedding_provider import EmbeddingProvider
from app.search.embeddings import embed_chunks
from app.search.vector_store import VectorStore


def index_folder(
    folder: str | Path,
    provider: EmbeddingProvider,
    store: VectorStore,
    settings: ChunkSettings | None = None,
) -> IndexReport:
    settings = settings or ChunkSettings(max_chars=1000, overlap_chars=100)
    started = perf_counter()
    print(f"Indexing: parsing folder {folder}", flush=True)
    documents = parse_folder(folder)
    print(
        f"Parsing complete: {len(documents)} files in {perf_counter() - started:.1f}s", flush=True
    )
    started = perf_counter()
    results = chunk_documents(prepare_documents(documents), settings)
    chunks = [chunk for result in results for chunk in result.chunks]
    if not chunks:
        raise ValueError("No text chunks available; review parsing issues before indexing")
    print(
        f"Cleaning/chunking complete: {len(chunks)} chunks in {perf_counter() - started:.1f}s",
        flush=True,
    )
    started = perf_counter()
    print("Indexing: token checks and embedding batches...", flush=True)
    embedded = embed_chunks(chunks, provider)
    print(
        f"Embedding complete: {len(embedded.embeddings)} vectors in "
        f"{perf_counter() - started:.1f}s",
        flush=True,
    )
    started = perf_counter()
    print("Indexing: saving vectors to Chroma...", flush=True)
    stored = store.upsert(embedded)
    print(f"Chroma save complete: {stored} vectors in {perf_counter() - started:.1f}s", flush=True)
    counts = Counter(record.chunk.source.relative_path for record in embedded.embeddings)
    return IndexReport(
        discovery_id=results[0].document.source.discovery_id,
        folder_name=results[0].document.source.folder_name,
        model=embedded.info,
        chunk_settings=settings,
        stored_chunks=stored,
        collection_count=store.count(),
        files=[
            FileIndexReport(
                relative_path=result.document.source.relative_path,
                chunk_count=counts[result.document.source.relative_path],
                issues=result.document.issues,
            )
            for result in results
        ],
    )
