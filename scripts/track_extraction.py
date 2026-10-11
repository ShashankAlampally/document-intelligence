"""Track a live extraction or inspect retrieval only, using an existing discovery ID."""

import argparse
import json
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.graph.workflow import extract_field_group
from app.agents.extraction.models.field_catalog import FIELD_GROUPS
from app.agents.extraction.models.validation_batches import (
    VALIDATION_MAX_CHARS,
    VALIDATION_MAX_CHUNKS,
    VALIDATION_MAX_EVIDENCE_CHARS,
)
from app.agents.extraction.prompts.retrieval_plan import retrieval_plan
from app.agents.shared.retrieve_evidence import retrieve_evidence
from app.config import Settings
from app.schemas.search import SearchFilters
from app.search.chroma_store import ChromaVectorStore
from app.search.local_embeddings import LocalEmbeddingProvider
from app.shared.groq_client import GroqModel
from app.tools.document_search import SearchInput, SearchTool
from scripts.pipeline_report import save_record
from scripts.pipeline_tracking import TrackingModel, TrackingSearch
from scripts.track_combined_extraction import track_combined_extraction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    parser.add_argument("--retrieval-only", action="store_true", help="No Groq calls")
    parser.add_argument("--group", choices=list(FIELD_GROUPS), action="append")
    parser.add_argument("--resume-from", type=str, help="Prior trace JSON; requires --group")
    parser.add_argument("--baseline", type=str, help="Saved extraction JSON to compare")
    args = parser.parse_args()
    settings = Settings()
    started = perf_counter()
    store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
    if not store.list_chunks(SearchFilters(discovery_id=args.discovery_id)):
        parser.error("No stored chunks for this discovery ID in the configured collection")
    tool = SearchTool(LocalEmbeddingProvider(settings), store, args.discovery_id)
    model = None if args.retrieval_only else GroqModel(settings)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = settings.output_dir / f"pipeline-{args.discovery_id}-{stamp}"
    record = dict(
        discovery_id=str(args.discovery_id),
        model=settings.llm_model,
        mode="retrieval_only" if args.retrieval_only else "live_extraction",
        status="running",
        pipeline_version="combined_validation_v2",
        fields={},
        trace=[],
        error=None,
    )
    if args.baseline:
        baseline = json.loads(open(args.baseline).read())
        if baseline.get("discovery_id") != str(args.discovery_id):
            parser.error("Baseline must use the same discovery ID")
        record["baseline"] = baseline
    groups = {name: FIELD_GROUPS[name] for name in args.group} if args.group else FIELD_GROUPS
    if args.resume_from:
        if not args.group or args.retrieval_only:
            parser.error("--resume-from requires explicit --group choices and live extraction")
        previous = json.loads(open(args.resume_from).read())
        if previous.get("discovery_id") != str(args.discovery_id):
            parser.error("Prior run must use the same discovery ID")
        record["fields"] = previous["fields"].copy()
        record["trace"] = previous["trace"].copy()
        record["resumed_from"] = args.resume_from
        record["prior_elapsed_seconds"] = previous.get("elapsed_seconds")
        record["baseline"] = previous.get("baseline", record.get("baseline", {}))
        for names in groups.values():
            for name in names:
                record["fields"].pop(name, None)
    print(f"Tracking output: {directory}", flush=True)
    record["configuration"] = {
        "embedding": store.info.model_dump(mode="json"),
        "collection": settings.vector_collection,
        "reranker_model": settings.reranker_model,
        "default_search": SearchInput(query="configuration").resolve(settings).model_dump(),
        "llm_max_tokens": settings.llm_max_tokens,
        "evidence_chars": 12000,
        "evidence_chunks": 15,
        "validation_payload_chars": VALIDATION_MAX_CHARS,
        "validation_evidence_chars": VALIDATION_MAX_EVIDENCE_CHARS,
        "validation_evidence_chunks": VALIDATION_MAX_CHUNKS,
    }
    save_record(directory, record)
    tool = TrackingSearch(tool, directory)
    if model is not None:
        model = TrackingModel(model, directory)
    try:
        if not args.retrieval_only and len(groups) > 1:
            track_combined_extraction(model, tool, groups, directory, record)
        else:
            for index, (group, names) in enumerate(groups.items(), 1):
                print(f"[{index}/{len(groups)}] {group}: retrieving evidence", flush=True)
                if args.retrieval_only:
                    state = ExtractionState(
                        requested_fields=names,
                        search_requests=retrieval_plan(names),
                        max_evidence_chunks=15,
                        max_evidence_chars=12000,
                    )
                    result = retrieve_evidence(state, {"search_documents": tool})
                    trace, error = result["trace"], result.get("error")
                else:
                    prior_trace = list(record["trace"])

                    def save_step(trace):
                        record["trace"] = prior_trace + [
                            {"field_group": group, **step} for step in trace
                        ]
                        save_record(directory, record)

                    result = extract_field_group(
                        model, {"search_documents": tool}, names, on_step=save_step
                    )
                    record["trace"] = prior_trace
                    trace, error = result.trace, result.error
                    record["validation_report"] = result.validation_report
                    record["fields"].update(
                        {name: field.model_dump() for name, field in result.fields.items()}
                    )
                record["trace"].extend({"field_group": group, **step} for step in trace)
                record["error"] = error
                if error:
                    record["status"] = "error"
                save_record(directory, record)
                print(
                    f"[{index}/{len(groups)}] {group}: {'failed' if error else 'saved'}", flush=True
                )
                if error:
                    break
        if record["status"] == "running":
            record["status"] = "completed"
    except KeyboardInterrupt:
        record["status"] = "interrupted"
        record["error"] = "Run interrupted; completed groups and events have been preserved"
    except Exception as error:
        record["status"] = "error"
        record["error"] = f"Run failed ({type(error).__name__}): {error}"
    finally:
        record["elapsed_seconds"] = round(perf_counter() - started, 2)
        save_record(directory, record)
    print(f"Status: {record['status']}; report: {directory / 'report.md'}", flush=True)
    if record["error"]:
        parser.exit(1, record["error"] + "\n")


if __name__ == "__main__":
    main()
