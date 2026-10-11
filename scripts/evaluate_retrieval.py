"""Compare real retrieval configurations against source-verified reference passages."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import UUID

from scripts.retrieval_evaluation import (
    evidence_groups,
    relevant,
    score,
    summarize,
    write_report,
    write_review,
)

CONFIGURATIONS = {
    "vector": {"mode": "vector", "rerank": False},
    "hybrid": {"mode": "hybrid", "rerank": False},
    "hybrid_rerank": {"mode": "hybrid", "rerank": True},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/retrieval/questions.json"))
    parser.add_argument("--bid1", type=UUID)
    parser.add_argument("--bid2", type=UUID)
    parser.add_argument("--k", type=int, default=5, choices=range(1, 21))
    parser.add_argument(
        "--configurations", nargs="+", choices=CONFIGURATIONS, default=list(CONFIGURATIONS)
    )
    parser.add_argument("--output", type=Path, default=Path("evaluation/retrieval/results.json"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--candidates", type=int, choices=range(5, 101), default=20)
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    questions = dataset["questions"]
    if len(questions) < 15 or len({q["id"] for q in questions}) != len(questions):
        parser.error("Need at least 15 uniquely identified questions")
    if any(not q["expected_passages"] or not q["question"].strip() for q in questions):
        parser.error("Every scored question needs a question and expected passages")
    write_review(dataset, args.dataset.parent / "QUESTIONS.md")
    if args.prepare_only:
        print(f"Prepared {len(questions)} questions: {args.dataset.parent / 'QUESTIONS.md'}")
        return
    if not args.bid1 or not args.bid2:
        parser.error("Provide --bid1 and --bid2 current indexed discovery IDs")
    # Lazy imports keep preparation and metric tests independent of model dependencies.
    from app.api.workspace.runtime import PipelineRuntime
    from app.config import Settings
    from app.schemas.search import SearchFilters
    from app.tools.document_search import SearchInput, SearchTool

    runtime = PipelineRuntime(Settings())
    uploads = {"Bid1": str(args.bid1), "Bid2": str(args.bid2)}
    runtime.require_uploads([args.bid1, args.bid2])
    index_fingerprints = {}
    indexed_hits = {}
    for bid, upload in uploads.items():
        chunks = runtime.store.list_chunks(SearchFilters(discovery_id=UUID(upload)))
        if not chunks:
            parser.error(f"{bid} has no chunks in the active collection; index it first")
        if any(chunk.source.folder_name != bid for chunk in chunks):
            parser.error(f"{bid} ID points to a different bid folder")
        indexed_hits[bid] = [
            dict(
                discovery_id=upload,
                file_name=c.source.file_name,
                page_number=c.page_number,
                text=c.text,
                content_type=c.content_type,
            )
            for c in chunks
        ]
        fingerprint = [
            (str(c.chunk_id), c.text) for c in sorted(chunks, key=lambda c: str(c.chunk_id))
        ]
        index_fingerprints[bid] = dict(
            chunks=len(chunks), sha256=hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest()
        )
    record = dict(
        status="running",
        created_at=datetime.now(timezone.utc).isoformat(),
        dataset_sha256=hashlib.sha256(raw).hexdigest(),
        dataset_status=dataset["status"],
        k=args.k,
        uploads=uploads,
        index_fingerprints=index_fingerprints,
        embedding=runtime.provider.info.model_dump(),
        collection=runtime.settings.vector_collection,
        reranker=dict(
            model=runtime.settings.reranker_model, revision=runtime.settings.reranker_revision
        ),
        configurations={
            name: SearchInput(
                query="configuration",
                top_k=args.k,
                vector_candidates=args.candidates,
                keyword_candidates=args.candidates,
                rerank_candidates=args.candidates,
                **CONFIGURATIONS[name],
            )
            .resolve(runtime.settings)
            .model_dump()
            for name in args.configurations
        },
        results=[],
        summary=[],
    )
    record["metric_rule"] = (
        "Bid + normalized filename + physical page + whole-token anchors (decoded table cells); "
        "OR within evidence_id, AND across units; supporting context excluded."
    )
    record["reference_units_absent_from_index"] = [
        dict(
            id=q["id"],
            unit=unit,
            bid=alternatives[0]["bid"],
            file=alternatives[0]["file"],
            page=alternatives[0]["page"],
        )
        for q in questions
        for unit, alternatives in evidence_groups(q["expected_passages"]).items()
        if not any(
            relevant(hit, ref, uploads) for ref in alternatives for hit in indexed_hits[ref["bid"]]
        )
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        record["summary"] = summarize(record["results"], args.configurations)
        args.output.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        write_report(record, args.output.with_suffix(".md"))

    save()
    for name in args.configurations:
        for q in questions:
            print(f"{name} / {q['id']}: {q['question']}", flush=True)
            started = perf_counter()
            row = dict(id=q["id"], question=q["question"], bids=q["bids"], configuration=name)
            try:
                tool = SearchTool(
                    runtime.provider,
                    runtime.store,
                    [UUID(uploads[bid]) for bid in q["bids"]],
                    options={**record["configurations"][name], "top_k": args.k},
                    settings=runtime.settings,
                    keyword_search=runtime.keyword_search,
                    reranker=runtime.reranker,
                )
                hits = tool.run({"query": q["question"]})
                key = (
                    "rerank_score"
                    if CONFIGURATIONS[name]["rerank"]
                    else (
                        "retrieval_score"
                        if CONFIGURATIONS[name]["mode"] == "hybrid"
                        else "similarity"
                    )
                )
                hits = sorted(hits, key=lambda hit: (-(hit.get(key) or 0), hit["chunk_id"]))[
                    : args.k
                ]
                row.update(hits=hits, metrics=score(hits, q["expected_passages"], uploads, args.k))
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
            row["elapsed_seconds"] = round(perf_counter() - started, 3)
            record["results"].append(row)
            save()
    record["status"] = (
        "completed" if all("metrics" in row for row in record["results"]) else "incomplete"
    )
    save()
    print(f"Saved {args.output} and {args.output.with_suffix('.md')}")
    if record["status"] != "completed":
        parser.exit(1, "One or more searches failed; inspect the recorded errors.\n")


if __name__ == "__main__":
    main()
