"""Keep reported evidence gaps consistent with the graph's search decision."""


def enforce_search_decision(decision, question, evidence, max_queries):
    known_ids = {item["chunk_id"] for item in evidence}
    gaps = [gap.strip() for gap in decision.missing_information if gap.strip()]
    for part in decision.coverage:
        if not part.requested_part.strip():
            raise ValueError("Coverage needs a requested part")
        if not set(part.source_chunk_ids).issubset(known_ids):
            raise ValueError("Coverage cites evidence that was not retrieved")
        if part.status == "missing":
            gaps.append(part.requested_part.strip())
        elif not part.source_chunk_ids:
            raise ValueError("Supported or explicitly unavailable parts need citations")
    decision.missing_information = list(dict.fromkeys(gaps))
    forced = decision.action == "answer" and bool(gaps)
    if forced:
        decision.action = "search_more"
        decision.status = "not_found"
        decision.answer = ""
        decision.source_chunk_ids = []
        # Use the user's question for scope; do not invent document facts or categories.
        decision.search_queries = [f"{question}\nFocus: {gap}" for gap in gaps[:max_queries]]
    return forced
