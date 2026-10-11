"""One model call decides Q&A, extraction or a direct conversational reply."""

from time import perf_counter

from app.agents.planner.models.task import TaskChoice
from app.agents.planner.prompts.instructions import ROUTING_INSTRUCTIONS
from app.agents.qa.models.answers import QuestionAnswer


def choose_workflow(state, model) -> dict:
    started = perf_counter()
    messages = [
        {
            "role": "system",
            "content": ROUTING_INSTRUCTIONS
            + f"\nSelected upload count: {len(state.discovery_ids)}",
        },
        {"role": "user", "content": state.request},
    ]
    try:
        response = model.complete(
            messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "workflow_choice",
                    "strict": True,
                    "schema": TaskChoice.model_json_schema(),
                },
            },
        )
        if response["finish_reason"] == "length":
            raise ValueError("Routing output was truncated")
        choice = TaskChoice.model_validate_json(response["message"].get("content") or "")
        update = {"choice": choice}
        if choice.task == "reply":
            if not choice.message or not choice.message.strip():
                raise ValueError("Direct reply must have text")
            update["qa_result"] = QuestionAnswer(status="direct_response", answer=choice.message)
        update["trace"] = [
            {
                "step": "choose_workflow",
                "input": messages,
                "output": choice.model_dump(),
                "usage": response["usage"],
                "latency_seconds": perf_counter() - started,
            }
        ]
        return update
    except Exception as error:
        return {
            "error": f"Workflow selection failed ({type(error).__name__})",
            "trace": [
                {
                    "step": "choose_workflow",
                    "error": type(error).__name__,
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
