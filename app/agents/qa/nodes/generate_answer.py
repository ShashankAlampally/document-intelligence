"""Produce a structured answer and check its source IDs against retrieved evidence."""

import json
from time import perf_counter

from app.agents.qa.graph.state import WorkflowState
from app.agents.qa.models.answers import AnswerDraft
from app.agents.qa.models.response_checks import checked_answer, response_schema
from app.agents.qa.prompts.instructions import ANSWER_INSTRUCTIONS


def generate_answer(state: WorkflowState, model) -> dict:
    if not state.evidence:
        draft = AnswerDraft(
            status="not_found", answer="Not found in documents", source_chunk_ids=[]
        )
        return {
            "draft": draft,
            "trace": state.trace
            + [
                {
                    "step": "generate_answer",
                    "input": [],
                    "output": draft.model_dump(),
                    "skipped_model": True,
                    "latency_seconds": 0,
                }
            ],
        }
    started = perf_counter()
    messages = (
        [{"role": "system", "content": ANSWER_INSTRUCTIONS}]
        + state.messages
        + [
            {"role": "user", "content": "Retrieved evidence:\n" + json.dumps(state.evidence)},
        ]
    )
    messages.append(
        {
            "role": "user",
            "content": (
                "This is the final answer after the additional search round. "
                "Answer supported parts and state any remaining gaps. "
                "Do not request more searches. "
                "Previously missing information: " + json.dumps(state.missing_information)
            ),
        }
    )
    if state.trace:
        gaps = state.trace[-1].get("selection", {}).get("queries_without_selected_evidence", [])
        if gaps:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "These searches contributed no selected evidence; "
                        "do not assume they are covered: "
                        + json.dumps(gaps)
                    ),
                }
            )
    try:
        response = model.complete(
            messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "document_answer",
                    "strict": True,
                    "schema": response_schema(AnswerDraft, state.evidence),
                },
            },
        )
        if response["finish_reason"] == "length":
            raise ValueError("Answer was truncated")
        draft = AnswerDraft.model_validate_json(response["message"].get("content") or "")
        draft = checked_answer(draft, state.evidence)
        return {
            "draft": draft,
            "trace": state.trace
            + [
                {
                    "step": "generate_answer",
                    "input": messages,
                    "output": draft.model_dump(),
                    "usage": response["usage"],
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
    except Exception as error:
        return {
            "error": f"Answer generation failed ({type(error).__name__})",
            "trace": state.trace
            + [
                {
                    "step": "generate_answer",
                    "error": type(error).__name__,
                    "error_detail": str(error),
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
