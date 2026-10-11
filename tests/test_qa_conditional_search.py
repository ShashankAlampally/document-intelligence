"""Exercise real conditional QA edges with offline model/search responses."""

import json

import pytest

from app.agents.qa.graph.workflow import answer_question
from scripts.evaluate_qa import run_questions
from scripts.qa_behavior import TrackedQAModel, summarize_behavior


def answer(ids, text="Deadline July 9; warranty three years."):
    return dict(status="found", answer=text, source_chunk_ids=ids)


def decision(action="search_more", queries=None):
    return dict(
        action=action,
        status="not_found",
        answer="",
        source_chunk_ids=[],
        search_queries=queries or ["Staff laptop warranty"],
        missing_information=["Staff laptop warranty"],
    )


class SequenceModel:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return dict(
            message={"content": json.dumps(response)},
            usage={"total_tokens": 12},
            finish_reason="stop",
        )


class Search:
    def __init__(self, *, fail_additional=False, empty=False):
        self.calls = []
        self.fail_additional = fail_additional
        self.empty = empty

    def run(self, request):
        self.calls.append(request)
        if len(self.calls) > 1 and self.fail_additional:
            raise RuntimeError("Search unavailable")
        if self.empty:
            return []
        initial = len(self.calls) == 1
        return [
            dict(
                chunk_id="deadline" if initial else "warranty",
                file_name="rfp.pdf",
                page_number=1 if initial else 2,
                section=None,
                text="Deadline July 9." if initial else "Staff laptop warranty three years.",
                similarity=0.8,
            )
        ]

    def add_heading_context(self, evidence):
        return [{**item, "heading_context": {"heading": "Requirements"}} for item in evidence]


def test_sufficient_evidence_returns_after_one_call():
    draft = {
        **answer(["deadline"], "Deadline July 9."),
        "action": "answer",
        "search_queries": [],
        "missing_information": [],
    }
    raw, search = SequenceModel([draft]), Search()
    model = TrackedQAModel(raw)
    result = answer_question("Deadline?", model, {"search_documents": search})
    assert result.status == "found"
    assert len(raw.calls) == len(search.calls) == 1
    behavior = summarize_behavior(result.trace, model.calls)
    assert behavior["decision"] == "answer"
    assert behavior["model_call_count"] == 1
    assert not behavior["additional_search_used"]
    schema = raw.calls[0][1]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["source_chunk_ids"]["items"]["enum"] == ["deadline"]
    assert "similarity" not in raw.calls[0][0][-1]["content"]
    assert "heading_context" in raw.calls[0][0][-1]["content"]


def test_missing_information_runs_one_additional_round_and_retains_initial_evidence():
    raw, search = SequenceModel([decision(), answer(["deadline", "warranty"])]), Search()
    model = TrackedQAModel(raw)
    result = answer_question("Deadline and warranty?", model, {"search_documents": search})
    assert result.status == "found"
    assert len(raw.calls) == len(search.calls) == 2
    assert {source["chunk_id"] for source in result.sources} == {"deadline", "warranty"}
    behavior = summarize_behavior(result.trace, model.calls)
    assert behavior["model_call_count"] == 2
    assert behavior["additional_search_used"]
    assert behavior["planned_queries"] == ["Staff laptop warranty"]
    assert behavior["total_tokens"] == 24
    assert [item["round"] for item in behavior["search_rounds"]] == ["initial", "additional"]


def test_search_failure_stops_before_second_model_call():
    model = TrackedQAModel(SequenceModel([decision()]))
    result = answer_question(
        "Deadline and warranty?", model, {"search_documents": Search(fail_additional=True)}
    )
    assert result.status == "error"
    assert len(model.calls) == 1
    behavior = summarize_behavior(result.trace, model.calls)
    assert behavior["additional_search_used"]
    assert behavior["search_rounds"][-1]["error"]


def test_empty_initial_evidence_can_trigger_search_instead_of_immediate_abstention():
    raw = SequenceModel([decision()])
    result = answer_question("Warranty?", raw, {"search_documents": Search(empty=True)})
    assert result.status == "not_found"
    assert len(raw.calls) == 1  # Final generation skips the model if still no evidence.
    assert result.trace[-1]["skipped_model"]


def test_search_request_accepts_missing_answer_placeholder_from_live_failure():
    planned = {**decision(), "answer": "Not found in documents"}
    raw, search = SequenceModel([planned, answer(["deadline", "warranty"])]), Search()
    result = answer_question("Deadline and warranty?", raw, {"search_documents": search})
    assert result.status == "found"
    assert len(raw.calls) == len(search.calls) == 2
    assert result.trace[1]["output"]["answer"] == ""


@pytest.mark.parametrize(
    "response",
    [
        decision(queries=[" "]),
        decision(queries=[f"Query {n}" for n in range(7)]),
        {**decision(), "source_chunk_ids": ["deadline"]},
        {**decision(), "answer": "Unsupported factual answer"},
    ],
)
def test_invalid_search_plan_does_not_execute_more_tools(response):
    search = Search()
    result = answer_question("Warranty?", SequenceModel([response]), {"search_documents": search})
    assert result.status == "error"
    assert len(search.calls) == 1


def test_evaluation_json_records_two_calls_and_provider_error(tmp_path):
    record = dict(
        status="prepared",
        pairs=[
            dict(
                id=1,
                question="Deadline and warranty?",
                reference_answer="Do not send this",
                reference_evidence="Hidden",
            )
        ],
        results=[],
    )
    model = SequenceModel([decision(), TimeoutError("Provider timed out")])
    run_questions(record, tmp_path, model, Search())
    saved = json.loads((tmp_path / "results.json").read_text())
    behavior = saved["results"][0]["behavior"]
    assert saved["status"] == "error"
    assert behavior["model_call_count"] == 2
    assert behavior["successful_model_calls"] == 1
    assert behavior["model_calls"][1]["error_detail"] == "Provider timed out"
    assert saved["run_summary"]["two_call_questions"] == 1
    assert saved["run_summary"]["error_questions"] == 1
    assert all("Do not send this" not in json.dumps(messages) for messages, _ in model.calls)


def test_reported_gap_overrides_immediate_answer_without_an_extra_planning_call():
    partial = {
        **answer(["deadline"], "Deadline July 9; warranty not found."),
        "action": "answer",
        "search_queries": [],
        "missing_information": ["Staff laptop warranty"],
    }
    raw, search = SequenceModel([partial, answer(["deadline", "warranty"])]), Search()
    tracked = TrackedQAModel(raw)
    result = answer_question("Deadline and warranty?", tracked, {"search_documents": search})
    assert result.status == "found"
    assert len(raw.calls) == len(search.calls) == 2
    assert "Focus: Staff laptop warranty" in search.calls[1]["query"]
    behavior = summarize_behavior(result.trace, tracked.calls)
    assert behavior["model_decision"] == "answer"
    assert behavior["decision"] == "search_more"
    assert behavior["search_forced_by_gaps"]


def test_coverage_gap_triggers_search_even_if_missing_information_is_empty():
    partial = {
        **answer(["deadline"]),
        "action": "answer",
        "search_queries": [],
        "missing_information": [],
        "coverage": [
            dict(requested_part="Deadline", status="supported", source_chunk_ids=["deadline"]),
            dict(requested_part="Warranty", status="missing", source_chunk_ids=[]),
        ],
    }
    raw, search = SequenceModel([partial, answer(["deadline", "warranty"])]), Search()
    result = answer_question("Deadline and warranty?", raw, {"search_documents": search})
    assert len(raw.calls) == 2
    assert result.trace[1]["output"]["missing_information"] == ["Warranty"]


def test_explicit_unavailability_with_evidence_can_stop_after_one_call():
    draft = {
        **answer(["deadline"], "The document explicitly says the date is not yet determined."),
        "action": "answer",
        "search_queries": [],
        "missing_information": [],
        "coverage": [
            dict(
                requested_part="Date",
                status="explicitly_unavailable",
                source_chunk_ids=["deadline"],
            )
        ],
    }
    raw, search = SequenceModel([draft]), Search()
    result = answer_question("Date?", raw, {"search_documents": search})
    assert result.status == "found"
    assert len(raw.calls) == 1


def test_unknown_coverage_citation_is_rejected_before_followup():
    draft = {
        **answer(["deadline"]),
        "action": "answer",
        "search_queries": [],
        "missing_information": [],
        "coverage": [
            dict(requested_part="Warranty", status="supported", source_chunk_ids=["invented"])
        ],
    }
    search = Search()
    result = answer_question("Warranty?", SequenceModel([draft]), {"search_documents": search})
    assert result.status == "error"
    assert len(search.calls) == 1
