"""Run document questions through the production QA agent, without answer leakage."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import UUID

from app.agents.qa.graph.workflow import answer_question
from app.api.workspace.runtime import PipelineRuntime
from app.config import Settings
from app.tools.document_search import SearchInput, SearchTool
from scripts.qa_behavior import TrackedQAModel, summarize_behavior
from scripts.qa_reference import read_pairs


def save_results(directory, record):
    directory.mkdir(parents=True, exist_ok=True)
    behaviors = [item.get("behavior", {}) for item in record["results"]]
    record["run_summary"] = {
        "questions_saved": len(record["results"]),
        "one_call_questions": sum(item.get("model_call_count") == 1 for item in behaviors),
        "two_call_questions": sum(item.get("model_call_count") == 2 for item in behaviors),
        "zero_call_questions": sum(item.get("model_call_count") == 0 for item in behaviors),
        "additional_search_questions": sum(
            item.get("additional_search_used", False) for item in behaviors
        ),
        "total_model_calls": sum(item.get("model_call_count", 0) for item in behaviors),
        "total_tokens": sum(item.get("total_tokens", 0) for item in behaviors),
        "error_questions": sum(item["status"] == "error" for item in record["results"]),
        "elapsed_question_seconds": round(
            sum(item.get("elapsed_seconds", 0) for item in record["results"]), 2
        ),
    }
    (directory / "results.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def run_questions(record, directory, model, tool, question_ids=None):
    completed = {item["id"] for item in record["results"] if item["status"] != "error"}
    record["status"] = "running"
    record.pop("error", None)
    save_results(directory, record)
    try:
        for pair in record["pairs"]:
            if pair["id"] in completed or (question_ids and pair["id"] not in question_ids):
                continue
            print(f"Q{pair['id']}: {pair['question']}", flush=True)
            started = perf_counter()
            tracked_model = TrackedQAModel(model)
            result = answer_question(pair["question"], tracked_model, {"search_documents": tool})
            item = {
                "id": pair["id"],
                **result.model_dump(),
                "elapsed_seconds": round(perf_counter() - started, 2),
                "behavior": summarize_behavior(result.trace, tracked_model.calls),
            }
            record["results"] = [old for old in record["results"] if old["id"] != pair["id"]] + [
                item
            ]
            save_results(directory, record)
            print(
                f"Q{pair['id']}: {result.status}; {len(tracked_model.calls)} QA model calls; saved",
                flush=True,
            )
            if result.error:
                record["status"] = "error"
                break
        else:
            record["status"] = (
                "completed" if len(record["results"]) == len(record["pairs"]) else "partial"
            )
    except KeyboardInterrupt:
        record["status"] = "interrupted"
    except Exception as error:
        record["status"] = "error"
        record["error"] = type(error).__name__
    finally:
        save_results(directory, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    parser.add_argument("document", type=Path)
    parser.add_argument(
        "--resume", type=Path, help="Existing results.json; skips successful questions"
    )
    parser.add_argument("--question", type=int, action="append", help="Run selected question IDs")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Extract pairs into JSON without model calls",
    )
    args = parser.parse_args()
    pairs = read_pairs(args.document)
    settings = Settings()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = settings.output_dir / f"qa-evaluation-{args.discovery_id}-{stamp}"
    record = dict(
        discovery_id=str(args.discovery_id),
        document=str(args.document.resolve()),
        model=settings.llm_model,
        status="prepared",
        pairs=pairs,
        results=[],
        pipeline="production QA agent; website planner bypassed",
        pipeline_version="coverage_qa_v2",
        configuration={
            "search": SearchInput(query="configuration").resolve(settings).model_dump(),
            "qa_search_rounds": "initial plus at most one conditional follow-up",
            "qa_top_k": settings.qa_search_top_k,
            "qa_max_followup_queries": settings.qa_max_followup_queries,
        },
    )
    if args.resume:
        record = json.loads(args.resume.read_text(encoding="utf-8"))
        if record["discovery_id"] != str(args.discovery_id) or record["pairs"] != pairs:
            parser.error("Resume must match both discovery ID and reference document")
        if record.get("pipeline_version") != "coverage_qa_v2":
            parser.error("Start a new run; old QA results cannot be mixed with the new pipeline")
        directory = args.resume.parent
    if args.question and not set(args.question).issubset({pair["id"] for pair in pairs}):
        parser.error("Unknown question ID")
    save_results(directory, record)
    print(f"Output: {directory}", flush=True)
    if not args.prepare_only:
        runtime = PipelineRuntime(settings)
        runtime.require_uploads([args.discovery_id])
        tool = SearchTool(
            runtime.provider,
            runtime.store,
            args.discovery_id,
            settings=settings,
            keyword_search=runtime.keyword_search,
            reranker=runtime.reranker,
        )
        run_questions(record, directory, runtime.model, tool, args.question)
    print(f"Status: {record['status']}; answers: {directory / 'results.json'}", flush=True)
    if record["status"] == "error":
        parser.exit(1)


if __name__ == "__main__":
    main()
