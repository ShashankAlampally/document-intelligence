"""Reuse retrieval while preparing and combining evidence for QA's two rounds."""

import json

from app.agents.shared.evidence_content import model_evidence
from app.agents.shared.retrieve_evidence import retrieve_evidence
from app.agents.shared.select_evidence import select_evidence


def retrieve_qa_evidence(state, tools, *, additional=False):
    try:
        return prepare_qa_evidence(state, tools, additional=additional)
    except Exception as error:
        return {
            "error": f"QA evidence preparation failed ({type(error).__name__})",
            "trace": state.trace
            + [
                {
                    "step": "retrieve_evidence",
                    "round": "additional" if additional else "initial",
                    "input": [{"query": query} for query in state.search_queries],
                    "error": type(error).__name__,
                    "error_detail": str(error),
                }
            ],
        }


def prepare_qa_evidence(state, tools, *, additional=False):
    result = retrieve_evidence(state, tools)
    if result.get("error"):
        result["trace"][-1]["round"] = "additional" if additional else "initial"
        return result
    step = result["trace"][-1]
    candidates = [item["chunks"] for item in step["search_results"]]
    if additional:
        candidates.insert(0, state.evidence)
    search = tools["search_documents"]
    prepared = []
    for chunks in candidates:
        if hasattr(search, "add_heading_context"):
            chunks = search.add_heading_context(chunks)
        prepared.append([model_evidence(chunk) for chunk in chunks])
    supporting = []
    if hasattr(search, "qa_supporting_passages"):
        seeds = [chunk for group in prepared for chunk in group]
        supporting = search.qa_supporting_passages(seeds)
        # Original ranked passages retain priority; continuations use the same budget.
        prepared.append([model_evidence(chunk) for chunk in supporting])
    decisions = []
    evidence = select_evidence(
        prepared,
        max_chunks=state.max_evidence_chunks,
        max_chars=state.max_evidence_chars,
        deduplicate_content=True,
        decisions=decisions,
    )
    selected = {item["chunk_id"] for item in evidence}
    selection = {
        "decisions": decisions,
        "candidate_count": len({item["chunk_id"] for group in prepared for item in group}),
        "selected_count": len(evidence),
        "serialized_chars": len(json.dumps(evidence, ensure_ascii=False)),
        "max_chunks": state.max_evidence_chunks,
        "max_chars": state.max_evidence_chars,
        "tables_omitted_by_budget": sorted(
            {
                item["table_id"]
                for group in prepared
                for item in group
                if item.get("table_id") and item["chunk_id"] not in selected
            }
        ),
        "queries_without_selected_evidence": [
            item["request"]
            for item in step["search_results"]
            if not any(chunk["chunk_id"] in selected for chunk in item["chunks"])
        ],
    }
    trace_step = {
        **step,
        "round": "additional" if additional else "initial",
        "output": evidence,
        "selection": selection,
        "previous_chunk_ids": [item["chunk_id"] for item in state.evidence] if additional else [],
        "supporting_passages": supporting,
    }
    return {"evidence": evidence, "trace": result["trace"][:-1] + [trace_step]}
