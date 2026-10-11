"""Capture actual QA model calls and summarize graph behavior for evaluation."""

from time import perf_counter


class TrackedQAModel:
    def __init__(self, model):
        self.model = model
        self.calls = []

    def complete(self, messages, **kwargs):
        started = perf_counter()
        call = {"number": len(self.calls) + 1, "status": "started"}
        self.calls.append(call)
        try:
            response = self.model.complete(messages, **kwargs)
            call.update(
                status="completed",
                usage=response.get("usage", {}),
                finish_reason=response.get("finish_reason"),
                message=response.get("message"),
            )
            return response
        except Exception as error:
            call.update(status="error", error=type(error).__name__, error_detail=str(error))
            raise
        finally:
            call["elapsed_seconds"] = round(perf_counter() - started, 2)


def summarize_behavior(trace, calls):
    decision = next((step for step in trace if step["step"] == "answer_or_search"), {})
    output = decision.get("output") or {}
    searches = [step for step in trace if step["step"] == "retrieve_evidence"]
    rounds = []
    for step in searches:
        selected = {item["chunk_id"] for item in step.get("output", [])}
        rounds.append(
            {
                "round": step.get("round", "initial"),
                "queries": step.get("input", []),
                "selection": step.get("selection", {}),
                "selected_chunk_ids": sorted(selected),
                "previous_chunk_ids": step.get("previous_chunk_ids", []),
                "candidates": [
                    {
                        "query": item["request"]["query"],
                        "chunk_ids": [chunk["chunk_id"] for chunk in item["chunks"]],
                    }
                    for item in step.get("search_results", [])
                ],
                "elapsed_seconds": step.get("latency_seconds"),
                "error": step.get("error"),
                "supporting_chunk_ids": [
                    item["chunk_id"] for item in step.get("supporting_passages", [])
                ],
            }
        )
    return {
        "model_call_count": len(calls),
        "successful_model_calls": sum(call["status"] == "completed" for call in calls),
        "decision": output.get("action"),
        "model_decision": (decision.get("model_decision") or output).get("action"),
        "search_forced_by_gaps": decision.get("search_forced_by_gaps", False),
        "coverage": output.get("coverage", []),
        "additional_search_used": any(step.get("round") == "additional" for step in searches),
        "missing_information": output.get("missing_information", []),
        "planned_queries": output.get("search_queries", []),
        "search_query_count": sum(len(step.get("input", [])) for step in searches),
        "search_rounds": rounds,
        "model_calls": calls,
        "total_tokens": sum(call.get("usage", {}).get("total_tokens", 0) for call in calls),
        "model_elapsed_seconds": round(sum(call["elapsed_seconds"] for call in calls), 2),
        "errors": [step for step in trace if step.get("error")],
        "call_count_scope": "QA calls only; excludes website planner and internal HTTP retries",
    }
