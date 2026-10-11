"""Balance ranked search results within a budget while retaining whole citations."""

import json
from itertools import zip_longest

from app.agents.shared.evidence_content import same_content

EXTRACTION_MAX_CHUNKS = 15
EXTRACTION_MAX_CHARS = 12000


def select_evidence(
    results: list[list[dict]],
    *,
    max_chunks: int | None = None,
    max_chars: int | None = None,
    deduplicate_content: bool = False,
    decisions: list | None = None,
) -> list[dict]:
    """Take rank 1 from each search, then rank 2, etc.; never trim a chunk's text.

    The character budget counts the complete JSON evidence, including metadata.
    It is a size bound, not an exact model-token count or a relevance guarantee.
    """
    selected = []
    seen = set()
    used_chars = 2  # JSON list brackets.
    for rank in zip_longest(*results):
        for item in rank:
            if item is None or item["chunk_id"] in seen:
                continue
            reason = None
            if deduplicate_content and any(same_content(item, saved) for saved in selected):
                reason = "duplicate_content"
            elif max_chunks is not None and len(selected) >= max_chunks:
                reason = "chunk_budget"
            if reason:
                if decisions is not None:
                    decisions.append({"chunk_id": item["chunk_id"], "decision": reason})
                continue
            cost = len(json.dumps(item, ensure_ascii=False))
            if selected:
                cost += 2  # Comma and space between records.
            if max_chars is not None and used_chars + cost > max_chars:
                if decisions is not None:
                    decisions.append({"chunk_id": item["chunk_id"], "decision": "character_budget"})
                continue
            if decisions is not None:
                decisions.append({"chunk_id": item["chunk_id"], "decision": "selected"})
            selected.append(item)
            seen.add(item["chunk_id"])
            used_chars += cost
    return selected
