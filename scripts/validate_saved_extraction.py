"""Validate saved 20-field drafts without repeating the seven extraction calls."""

import argparse
import json
from datetime import datetime, timezone
from uuid import UUID

from app.agents.extraction.models.validation_batches import validation_batches
from app.config import Settings
from app.schemas.search import SearchFilters
from app.search.chroma_store import ChromaVectorStore
from app.search.local_embeddings import LocalEmbeddingProvider
from app.shared.groq_client import GroqModel
from app.tools.document_search import SearchTool
from scripts.saved_extraction import load_saved_extraction
from scripts.saved_validation_run import run_saved_validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("saved_run", help="Previous output directory or its trace.json")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Check saved evidence and budgets; no Groq calls",
    )
    args = parser.parse_args()
    try:
        source_path, previous, state = load_saved_extraction(args.saved_run)
        batches = validation_batches(state.draft.fields, state.evidence)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Cannot load/validate saved drafts: {error}\n")
    print(
        f"Saved fields: {len(state.draft.fields)}; planned validation batches: {len(batches)}",
        flush=True,
    )
    print("The seven initial extraction calls will not be repeated.", flush=True)
    if args.prepare_only:
        print(
            json.dumps(
                [
                    {
                        "batch": index,
                        "fields": [f["name"] for f in batch["fields"]],
                        "evidence_chars": len(json.dumps(batch["evidence"], ensure_ascii=False)),
                        "payload_chars": len(json.dumps(batch, ensure_ascii=False)),
                    }
                    for index, batch in enumerate(batches, 1)
                ],
                indent=2,
            )
        )
        return
    settings = Settings()
    identity = UUID(previous["discovery_id"])
    store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
    if not store.list_chunks(SearchFilters(discovery_id=identity)):
        parser.exit(1, "Indexed upload is unavailable for possible correction searches\n")
    search = SearchTool(LocalEmbeddingProvider(settings), store, identity)
    model = GroqModel(settings)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = settings.output_dir / f"validation-{identity}-{stamp}"
    print(f"Validation output: {directory}", flush=True)
    record = run_saved_validation(state, previous, source_path, directory, model, search)
    print(f"Status: {record['status']}; report: {directory / 'report.md'}", flush=True)
    if record["error"]:
        parser.exit(1, record["error"] + "\n")


if __name__ == "__main__":
    main()
