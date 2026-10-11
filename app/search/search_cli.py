"""Index a folder or search locally persisted chunks from the terminal."""

import argparse
from pathlib import Path
from typing import get_args

from app.config import Settings
from app.schemas.chunks import ChunkSettings
from app.schemas.metadata import DocumentType
from app.schemas.retrieval import SearchTuning
from app.schemas.search import SearchFilters
from app.search.chroma_store import ChromaVectorStore
from app.search.cross_encoder_reranker import CrossEncoderReranker
from app.search.indexer import index_folder
from app.search.local_embeddings import LocalEmbeddingProvider
from app.search.service import search_documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, help="Override the configured Chroma directory")
    parser.add_argument("--collection", help="Override the configured collection name")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="Parse, embed, and save a new folder upload")
    index.add_argument("folder", type=Path)
    index.add_argument("--chunk-size", type=int, default=1000)
    index.add_argument("--overlap", type=int, default=100)
    search = commands.add_parser("search", help="Search saved chunks without reparsing files")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--folder-name")
    search.add_argument("--discovery-id")
    search.add_argument("--file-name")
    search.add_argument("--doc-type", choices=get_args(DocumentType))
    search.add_argument("--addendum-number", type=int)
    search.add_argument("--mode", choices=["vector", "hybrid"])
    search.add_argument("--vector-candidates", type=int)
    search.add_argument("--keyword-candidates", type=int)
    search.add_argument("--vector-weight", type=float)
    search.add_argument("--keyword-weight", type=float)
    search.add_argument("--rrf-k", type=int)
    search.add_argument("--field-name")
    search.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=None)
    search.add_argument("--rerank-candidates", type=int)
    args = parser.parse_args()
    try:
        config = Settings()
        path = args.db_path or config.vector_db_dir
        collection = args.collection or config.vector_collection
        provider = LocalEmbeddingProvider(config)
        if args.command == "index":
            chunk_settings = ChunkSettings(max_chars=args.chunk_size, overlap_chars=args.overlap)
            print("Loading model and indexing folder...", flush=True)
            store = ChromaVectorStore(path, collection, provider.info)
            report = index_folder(args.folder, provider, store, chunk_settings)
            manifest = path.parent / "manifests" / f"{report.discovery_id}.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            print(f"Folder: {report.folder_name}; discovery ID: {report.discovery_id}")
            print(
                f"Stored: {report.stored_chunks} chunks; "
                f"collection total: {report.collection_count}"
            )
            print(f"Database: {path.resolve()}\nIndex report: {manifest.resolve()}")
            for file in report.files:
                for issue in file.issues:
                    print(f"ISSUE {file.relative_path}: {issue.code}: {issue.message}")
            if any(issue.severity == "error" for file in report.files for issue in file.issues):
                parser.exit(
                    status=1, message="Available chunks saved; some files have parsing errors.\n"
                )
        else:
            filters = SearchFilters(
                folder_name=args.folder_name,
                discovery_id=args.discovery_id,
                file_name=args.file_name,
                doc_type=args.doc_type,
                addendum_number=args.addendum_number,
            )
            store = ChromaVectorStore(path, collection)
            options = SearchTuning(
                **{name: getattr(args, name) for name in SearchTuning.model_fields}
            ).resolve(config)
            hits = search_documents(
                args.query,
                provider,
                store,
                args.top_k,
                filters,
                options=options,
                reranker=CrossEncoderReranker(config),
            )
            print(
                f"Matches: {len(hits)}; mode={options.mode}; rerank={options.rerank} "
                "(retrieval scores are not confidence)"
            )
            for number, hit in enumerate(hits, start=1):
                chunk = hit.chunk
                score = hit.retrieval_score if hit.retrieval_score is not None else hit.similarity
                label = "RRF score" if hit.retrieval_score is not None else "cosine similarity"
                print(
                    f"\n{number}. {chunk.source.file_name}; page={chunk.page_number}; "
                    f"section={chunk.section}; {label}={score:.4f}"
                )
                print(
                    f"Folder: {chunk.source.folder_name}; discovery ID: {chunk.source.discovery_id}"
                )
                print(
                    f"Document type: {chunk.source.doc_type}; "
                    f"addendum number: {chunk.source.addendum_number}"
                )
                if hit.rerank_score is not None:
                    print(f"Rerank score: {hit.rerank_score:.4f}")
                print(chunk.text)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(status=1, message=f"Failed: {error}\n")


if __name__ == "__main__":
    main()
