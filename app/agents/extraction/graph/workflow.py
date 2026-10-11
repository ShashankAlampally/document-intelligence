"""Extract one field group using explicit retrieval and structured model output."""

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.graph.validation_workflow import build_extraction_graph
from app.agents.extraction.models.build_result import build_result
from app.agents.extraction.models.field_catalog import FIELD_NAMES
from app.agents.extraction.models.fields import ExtractionResult
from app.agents.extraction.nodes.extract_fields import extract_fields
from app.agents.extraction.prompts.retrieval_plan import retrieval_plan
from app.agents.extraction.prompts.search_queries import field_search_queries
from app.agents.shared.retrieval_graph import build_retrieval_graph
from app.agents.shared.select_evidence import EXTRACTION_MAX_CHARS, EXTRACTION_MAX_CHUNKS


def extract_group_state(model, available_tools, requested_fields, *, validate=True, on_step=None):
    tool = available_tools.get("search_documents")
    if tool is not None and hasattr(tool, "discovery_ids") and len(tool.discovery_ids) != 1:
        raise ValueError("Select one upload for structured field extraction")
    if not requested_fields or len(set(requested_fields)) != len(requested_fields):
        raise ValueError("Provide a non-empty list of unique fields")
    if not set(requested_fields).issubset(FIELD_NAMES):
        raise ValueError("Unknown assignment field")

    if validate:
        graph = build_extraction_graph(model, available_tools, on_step=on_step)
    else:
        graph = build_retrieval_graph(
            ExtractionState, available_tools, lambda state: extract_fields(state, model)
        )
    queries = field_search_queries(requested_fields)
    state = ExtractionState.model_validate(
        graph.invoke(
            ExtractionState(
                requested_fields=requested_fields,
                search_queries=queries,
                search_requests=retrieval_plan(requested_fields),
                search_top_k=5,
                max_evidence_chunks=EXTRACTION_MAX_CHUNKS,
                max_evidence_chars=EXTRACTION_MAX_CHARS,
            ),
            config={"recursion_limit": 10},
        )
    )
    return state


def extract_field_group(
    model, available_tools: dict, requested_fields: list[str], *, on_step=None
) -> ExtractionResult:
    return build_result(
        extract_group_state(model, available_tools, requested_fields, on_step=on_step)
    )
