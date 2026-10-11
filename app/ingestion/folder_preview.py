"""Save all parsed documents in a folder as combined JSON and readable text."""

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from app.ingestion.chunk_preview import format_chunks
from app.ingestion.pipeline import parse_folder
from app.ingestion.preparation import prepare_documents
from app.ingestion.preview_format import format_document
from app.schemas.chunks import ChunkedDocument, ChunkSettings
from app.schemas.documents import ParsedDocument
from app.schemas.prepared import PreparedDocument
from app.search.chunker import chunk_documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing PDFs and saved HTML")
    parser.add_argument("--output", type=Path, required=True, help="Combined output JSON path")
    parser.add_argument(
        "--prepare", action="store_true", help="Clean copies of parsed content before saving"
    )
    parser.add_argument(
        "--chunks", action="store_true", help="Prepare content and create text chunks"
    )
    parser.add_argument("--chunk-size", type=int, default=2000, help="Maximum characters per chunk")
    parser.add_argument("--overlap", type=int, default=200, help="Target overlap in characters")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("Output must use a .json extension")
    try:
        settings = ChunkSettings(max_chars=args.chunk_size, overlap_chars=args.overlap)
    except ValueError as error:
        parser.error(str(error))
    try:
        documents = parse_folder(args.folder)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.prepare or args.chunks:
        documents = prepare_documents(documents)
    results = chunk_documents(documents, settings) if args.chunks else documents
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model = ChunkedDocument if args.chunks else PreparedDocument if args.prepare else ParsedDocument
    adapter = TypeAdapter(list[model])
    args.output.write_bytes(adapter.dump_json(results, indent=2))
    text_path = args.output.with_suffix(".txt")
    formatter = format_chunks if args.chunks else format_document
    text_path.write_text("\n".join(map(formatter, results)), encoding="utf-8")
    failed = sum(any(issue.severity == "error" for issue in doc.issues) for doc in documents)
    print(
        f"Files: {len(documents)}; files with errors: {failed}; "
        f"issues: {sum(len(doc.issues) for doc in documents)}"
    )
    stage = (
        "text chunks" if args.chunks else "prepared content" if args.prepare else "raw extraction"
    )
    print(f"Stage: {stage}")
    if args.chunks:
        print(f"Chunks: {sum(len(result.chunks) for result in results)}")
    for doc in documents:
        print(
            f"{doc.source.relative_path}: text={len(doc.text_blocks)}, "
            f"tables={len(doc.tables)}, images={len(doc.images)}, issues={len(doc.issues)}"
        )
    print(f"JSON: {args.output}\nReadable text: {text_path}")
    if failed:
        parser.exit(status=1)


if __name__ == "__main__":
    main()
