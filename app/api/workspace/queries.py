"""Run the existing agents or standalone search and translate their results."""

import json
from uuid import uuid4

from fastapi import HTTPException

from app.agents.planner.graph.workflow import run_request
from app.api.workspace.files import save_json
from app.api.workspace.sources import source_passage
from app.api.workspace_contracts import DocumentReply, SelectedDocumentQuery
from app.tools.document_search import SearchTool


def query_tool(runtime, query: SelectedDocumentQuery) -> SearchTool:
    return SearchTool(
        runtime.provider,
        runtime.store,
        query.discovery_ids,
        options=query.model_dump(exclude={"question", "discovery_ids"}, exclude_none=True),
        settings=runtime.settings,
        keyword_search=runtime.keyword_search,
        reranker=runtime.reranker,
    )


def search_reply(runtime, query: SelectedDocumentQuery) -> DocumentReply:
    tool = query_tool(runtime, query)
    evidence = tool.run({"query": query.question})
    return DocumentReply(
        answer=f"Found {len(evidence)} passages." if evidence else "Not found in documents",
        sources=[source_passage(source) for source in evidence],
    )


def agent_reply(runtime, query: SelectedDocumentQuery) -> DocumentReply:
    tool = query_tool(runtime, query)
    result = run_request(
        query.question, query.discovery_ids, runtime.model, {"search_documents": tool}
    )
    trace = runtime.settings.log_dir / f"api-{uuid4()}.json"
    save_json(trace, result.model_dump_json(indent=2))
    if result.error:
        status = 502
        if "RateLimitError" in result.error:
            status = 429
        if "Timeout" in result.error:
            status = 504
        raise HTTPException(status, f"{result.error}. Please retry; a trace was saved.")
    if result.qa_result is not None:
        return DocumentReply(
            answer=result.qa_result.answer,
            sources=[source_passage(source) for source in result.qa_result.sources],
        )
    extraction = result.extraction_result
    if extraction is None:
        raise HTTPException(502, "Agent finished without an answer")
    path = runtime.settings.output_dir / f"fields-{query.discovery_ids[0]}.json"
    record = {
        "discovery_id": str(query.discovery_ids[0]),
        "model": runtime.settings.llm_model,
        **extraction.model_dump(exclude={"trace"}),
    }
    save_json(path, json.dumps(record, indent=2, ensure_ascii=False))
    sources = {}
    lines = []
    for name, field in extraction.fields.items():
        lines.append(f"{name}: {field.value or field.notes or 'Not found in documents'}")
        for source in field.sources:
            sources[source["chunk_id"]] = source
    return DocumentReply(
        answer="\n".join(lines), sources=[source_passage(source) for source in sources.values()]
    )
