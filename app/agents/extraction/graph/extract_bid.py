"""Extract seven groups first, then validate their combined draft."""

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.graph.validation_workflow import build_validation_graph
from app.agents.extraction.graph.workflow import extract_group_state
from app.agents.extraction.models.build_result import build_result
from app.agents.extraction.models.field_catalog import FIELD_GROUPS, FIELD_NAMES
from app.agents.extraction.models.fields import ExtractionDraft, ExtractionResult
from app.agents.shared.select_evidence import EXTRACTION_MAX_CHARS, EXTRACTION_MAX_CHUNKS


def extract_bid_fields(
    model, available_tools: dict, *, groups=None, on_group=None, on_step=None
) -> ExtractionResult:
    groups = FIELD_GROUPS if groups is None else groups
    combined = ExtractionState(
        requested_fields=[name for names in groups.values() for name in names],
        draft=ExtractionDraft(fields=[]),
        search_top_k=5,
        max_evidence_chunks=EXTRACTION_MAX_CHUNKS,
        max_evidence_chars=EXTRACTION_MAX_CHARS,
    )
    if (
        not combined.requested_fields
        or len(set(combined.requested_fields)) != len(combined.requested_fields)
        or not set(combined.requested_fields).issubset(FIELD_NAMES)
    ):
        raise ValueError("Provide known fields for extraction")
    for group_name, names in groups.items():
        state = extract_group_state(model, available_tools, names, validate=False)
        combined.trace.extend({"field_group": group_name, **step} for step in state.trace)
        if state.error:
            result = build_result(combined)
            result.status = "error"
            result.error = f"Group {group_name}: {state.error}"
            return result
        combined.draft.fields.extend(state.draft.fields)
        known = {item["chunk_id"] for item in combined.evidence}
        combined.evidence.extend(item for item in state.evidence if item["chunk_id"] not in known)
        if on_group is not None:
            on_group(group_name, build_result(state))
    graph = build_validation_graph(model, available_tools, on_step=on_step)
    final = ExtractionState.model_validate(graph.invoke(combined, config={"recursion_limit": 6}))
    return build_result(final)
