"""Answer immediately when supported, otherwise plan one additional search round."""

import json
from time import perf_counter

from app.agents.qa.models.answers import AnswerOrSearch
from app.agents.qa.models.response_checks import checked_answer, response_schema
from app.agents.qa.models.search_decision import enforce_search_decision
from app.agents.qa.prompts.instructions import ANSWER_INSTRUCTIONS, SEARCH_DECISION_INSTRUCTIONS


def answer_or_search(state, model):
    started = perf_counter()
    instructions = ANSWER_INSTRUCTIONS + SEARCH_DECISION_INSTRUCTIONS
    instructions += f"\nAt most {state.max_followup_queries} additional search queries are allowed."
    messages = [{"role": "system", "content": instructions}] + state.messages
    messages.append({"role": "user", "content": json.dumps(state.evidence, ensure_ascii=False)})
    response = {}
    try:
        schema = response_schema(AnswerOrSearch, state.evidence)
        schema["properties"]["search_queries"]["maxItems"] = state.max_followup_queries
        response = model.complete(
            messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "answer_or_search",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        if response["finish_reason"] == "length":
            raise ValueError("Answer/search decision was truncated")
        decision = AnswerOrSearch.model_validate_json(response["message"].get("content") or "")
        model_decision = decision.model_dump()
        question = state.messages[-1]["content"].split("\nSelected discovery IDs:")[0]
        forced = enforce_search_decision(
            decision, question, state.evidence, state.max_followup_queries
        )
        updates = {"decision": decision, "missing_information": decision.missing_information}
        if decision.action == "answer":
            if decision.search_queries:
                raise ValueError("An immediate answer must not request searches")
            updates["draft"] = checked_answer(decision, state.evidence)
        else:
            queries = list(dict.fromkeys(query.strip() for query in decision.search_queries))
            if not queries or any(not query for query in queries):
                raise ValueError("Additional search requires non-empty queries")
            if len(queries) > state.max_followup_queries:
                raise ValueError("Too many additional search queries")
            # A missing-answer placeholder is harmless when requesting more evidence.
            if (
                decision.answer.strip() not in ("", "Not found in documents")
                or decision.source_chunk_ids
            ):
                raise ValueError("A search decision must not contain an answer or citations")
            decision.answer = ""
            if decision.status != "not_found":
                raise ValueError("A search decision must use not_found status")
            updates["search_queries"] = queries
        updates["trace"] = state.trace + [
            {
                "step": "answer_or_search",
                "input": messages,
                "output": decision.model_dump(),
                "model_decision": model_decision,
                "search_forced_by_gaps": forced,
                "usage": response.get("usage", {}),
                "latency_seconds": perf_counter() - started,
            }
        ]
        return updates
    except Exception as error:
        return {
            "error": f"QA decision failed ({type(error).__name__})",
            "trace": state.trace
            + [
                {
                    "step": "answer_or_search",
                    "input": messages,
                    "error": type(error).__name__,
                    "error_detail": str(error),
                    "output": response.get("message"),
                    "usage": response.get("usage", {}),
                    "latency_seconds": perf_counter() - started,
                }
            ],
        }
