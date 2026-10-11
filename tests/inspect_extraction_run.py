"""Run one live extraction on an existing upload and save a separate experiment."""

import argparse
import json
from time import perf_counter
from uuid import UUID, uuid4

from app.agents.planner.graph.workflow import run_request
from app.api.workspace.runtime import PipelineRuntime
from app.config import Settings
from app.tools.document_search import SearchTool


class ProgressModel:
    def __init__(self, model):
        self.model = model
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        names = [
            line[2:].split(":", 1)[0]
            for line in messages[0]["content"].splitlines()
            if line.startswith("- ")
        ]
        print(f"Model call {self.calls}: {', '.join(names) or 'planner'}", flush=True)
        started = perf_counter()
        result = self.model.complete(messages, **kwargs)
        print(
            f"Completed in {perf_counter() - started:.1f}s; "
            f"tokens={result['usage'].get('total_tokens')}",
            flush=True,
        )
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    args = parser.parse_args()
    runtime = PipelineRuntime(Settings())
    runtime.require_uploads([args.discovery_id])
    tool = SearchTool(
        runtime.provider,
        runtime.store,
        args.discovery_id,
        settings=runtime.settings,
        keyword_search=runtime.keyword_search,
        reranker=runtime.reranker,
    )
    started = perf_counter()
    result = run_request(
        "Extract all 20 bid fields",
        args.discovery_id,
        ProgressModel(runtime.model),
        {"search_documents": tool},
    )
    label = f"extraction-3-fields-5-chunks-{uuid4()}"
    trace = runtime.settings.log_dir / f"{label}.json"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    extraction = result.extraction_result
    record = {
        "discovery_id": str(args.discovery_id),
        "model": runtime.settings.llm_model,
        "elapsed_seconds": perf_counter() - started,
        "trace": str(trace),
        "error": result.error,
    }
    if extraction is not None:
        record.update(extraction.model_dump(mode="json", exclude={"trace"}))
    output = runtime.settings.output_dir / f"{label}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Elapsed: {record['elapsed_seconds']:.1f}s\nOutput: {output}\nTrace: {trace}")
    if result.error:
        parser.exit(1, f"{result.error}\n")


if __name__ == "__main__":
    main()
