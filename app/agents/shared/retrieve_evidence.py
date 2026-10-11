"""Execute the specialist's explicit searches; no model/tool-selection call."""

import json
from time import perf_counter

from app.agents.shared.evidence_content import model_evidence
from app.agents.shared.select_evidence import select_evidence
from app.agents.shared.state import ToolState


def retrieve_evidence(state: ToolState, available_tools: dict) -> dict:
    started = perf_counter()
    requests = [{"query": query, "top_k": state.search_top_k} for query in state.search_queries]
    for request, name in zip(requests, getattr(state, "requested_fields", [])):
        request["field_name"] = name
    if state.search_requests:
        requests = state.search_requests
    try:
        search = available_tools["search_documents"]
        results = []
        for request in requests:
            found = search.run(request)
            if getattr(state, "requested_fields", []) and hasattr(search, "add_heading_context"):
                found = search.add_heading_context(found)
            results.append(found)
        extraction = bool(getattr(state, "requested_fields", []))
        decisions = []
        groups = {}
        for request, result in zip(requests, results):
            name = request.get("field_name", request["query"])
            groups.setdefault(name, []).append(result)
        # Seed every field before taking the extra topics of broad fields.
        # Then the selector takes rank 1 from each topic before rank 2.
        balanced = [searches[0] for searches in groups.values()]
        for searches in groups.values():
            balanced.extend(searches[1:])
        if extraction:
            balanced = [[model_evidence(item) for item in result] for result in balanced]
        evidence = select_evidence(
            balanced,
            max_chunks=state.max_evidence_chunks,
            max_chars=state.max_evidence_chars,
            deduplicate_content=extraction,
            decisions=decisions,
        )
        selected_ids = {item["chunk_id"] for item in evidence}
        return {
            "evidence": evidence,
            "trace": state.trace
            + [
                {
                    "step": "retrieve_evidence",
                    "input": requests,
                    "output": evidence,
                    "search_results": [
                        {"request": request, "chunks": result}
                        for request, result in zip(requests, results)
                    ],
                    "selection": {
                        "decisions": decisions,
                        "candidate_count": len(
                            {item["chunk_id"] for result in results for item in result}
                        ),
                        "selected_count": len(evidence),
                        "serialized_chars": len(json.dumps(evidence, ensure_ascii=False)),
                        "max_chunks": state.max_evidence_chunks,
                        "max_chars": state.max_evidence_chars,
                        "tables_omitted_by_budget": sorted(
                            {
                                item["table_id"]
                                for result in results
                                for item in result
                                if item.get("table_id") and item["chunk_id"] not in selected_ids
                            }
                        ),
                        "incomplete_table_ids": sorted(
                            {
                                item["table_id"]
                                for item in evidence
                                if item.get("table_id") and not item.get("table_complete")
                            }
                        ),
                        "queries_without_selected_evidence": [
                            request["query"]
                            for request, result in zip(requests, results)
                            if not any(item["chunk_id"] in selected_ids for item in result)
                        ],
                    },
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
    except Exception as error:
        return {
            "error": f"Search failed ({type(error).__name__})",
            "trace": state.trace
            + [
                {
                    "step": "retrieve_evidence",
                    "input": requests,
                    "error": type(error).__name__,
                    "error_detail": str(error),
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
