"""Convert retrieved evidence into the extraction agent's structured fields."""

import json
from time import perf_counter

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.models.check_fields import check_fields
from app.agents.extraction.models.fields import ExtractionDraft, FieldDraft
from app.agents.extraction.prompts.instructions import field_output_instructions


def extract_fields(state: ExtractionState, model) -> dict:
    started = perf_counter()
    # This final step needs the task and unique evidence, not the full tool history.
    messages = [
        {"role": "system", "content": field_output_instructions(state.requested_fields)},
        {"role": "user", "content": json.dumps(state.evidence, ensure_ascii=False)},
    ]
    messages.extend(state.messages)
    usage = {}
    response = {}
    model_called = False
    try:
        if not state.evidence:
            draft = ExtractionDraft(
                fields=[
                    FieldDraft(
                        name=name,
                        value=None,
                        source_chunk_ids=[],
                        confidence=0,
                        notes="Not found in retrieved evidence",
                    )
                    for name in state.requested_fields
                ]
            )
        else:
            schema = ExtractionDraft.model_json_schema()
            field_schema = schema["$defs"]["FieldDraft"]["properties"]
            field_schema["source_chunk_ids"]["items"]["enum"] = list(
                dict.fromkeys(item["chunk_id"] for item in state.evidence)
            )
            field_schema["name"]["enum"] = state.requested_fields
            model_called = True
            response = model.complete(
                messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "bid_fields",
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
            usage = response["usage"]
            if response["finish_reason"] == "length":
                raise ValueError("Field output was truncated")
            draft = ExtractionDraft.model_validate_json(response["message"].get("content") or "")
        check_fields(draft, state.evidence, state.requested_fields)
        return {
            "draft": draft,
            "trace": state.trace
            + [
                {
                    "step": "extract_fields",
                    "model_called": model_called,
                    "input": messages,
                    "output": draft.model_dump(),
                    "usage": usage,
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
    except Exception as error:
        error_message = f"Field extraction failed ({type(error).__name__})"
        if response.get("finish_reason") == "length":
            error_message = "Field output was truncated; increase RFP_LLM_MAX_TOKENS"
        return {
            "error": error_message,
            "trace": state.trace
            + [
                {
                    "step": "extract_fields",
                    "model_called": model_called,
                    "error": type(error).__name__,
                    "error_detail": str(error),
                    "output": (response.get("message") or {}).get("content"),
                    "finish_reason": response.get("finish_reason"),
                    "usage": usage,
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
