"""Inspect real embeddings for a folder without creating a vector-store index."""

import argparse
from pathlib import Path

from app.ingestion.pipeline import parse_folder
from app.ingestion.preparation import prepare_documents
from app.schemas.chunks import ChunkSettings
from app.search.chunker import chunk_documents
from app.search.embeddings import embed_chunks
from app.search.local_embeddings import LocalEmbeddingProvider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="Embedding preview JSON path")
    parser.add_argument("--query", help="Optionally generate a query embedding with the same model")
    parser.add_argument("--chunk-size", type=int, default=2000)
    parser.add_argument("--overlap", type=int, default=200)
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("Output must use a .json extension")
    try:
        settings = ChunkSettings(max_chars=args.chunk_size, overlap_chars=args.overlap)
        documents = parse_folder(args.folder)
        results = chunk_documents(prepare_documents(documents), settings)
        chunks = [chunk for result in results for chunk in result.chunks]
        if not chunks:
            parser.error("No text chunks available; review parsing issues before embedding")
        print(
            f"Files: {len(documents)}; initial chunks: {len(chunks)}. Loading embedding model...",
            flush=True,
        )
        embedded = embed_chunks(chunks, LocalEmbeddingProvider(), args.query)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(status=1, message=f"Embedding failed: {error}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Keep failed files/issues in the preview even if they produced no vectors.
    for result in results:
        result.chunks = [
            record.chunk
            for record in embedded.embeddings
            if record.chunk.source.relative_path == result.document.source.relative_path
        ]
    payload = {
        "documents": [result.model_dump(mode="json") for result in results],
        "embedding_result": embedded.model_dump(mode="json"),
    }
    import json

    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        f"Model: {embedded.info.model}",
        f"Revision: {embedded.info.revision}",
        f"Dimensions: {embedded.info.dimensions}; vectors: {len(embedded.embeddings)}",
        "Numbers below are the first 8 components, not full vectors or confidence scores.",
    ]
    for record in embedded.embeddings:
        chunk = record.chunk
        lines.extend(
            [
                f"\nChunk: {chunk.chunk_id}; file: {chunk.source.relative_path}; "
                f"page: {chunk.page_number}; section: {chunk.section}",
                f"Vector sample: {record.vector[:8]}",
                chunk.text,
            ]
        )
    if embedded.query:
        lines.extend(
            [
                f"\nQuery: {embedded.query.text}",
                f"Query vector sample: {embedded.query.vector[:8]}",
            ]
        )
    for document in documents:
        for issue in document.issues:
            lines.append(f"ISSUE {document.source.file_name}: {issue.code}: {issue.message}")
    args.output.with_suffix(".txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Vectors: {len(embedded.embeddings)}; dimensions: {embedded.info.dimensions}")
    print(f"JSON: {args.output}\nReadable text: {args.output.with_suffix('.txt')}")
    if any(issue.severity == "error" for doc in documents for issue in doc.issues):
        parser.exit(
            status=1, message="Saved available embeddings; some files have parsing errors.\n"
        )


if __name__ == "__main__":
    main()
