"""Direct specialist retrieval and answer formatting; no Groq calls."""

import json

import pytest

pytest.importorskip("langgraph")
from app.agents.qa.graph.workflow import answer_question


class FakeModel:
    def __init__(self, draft=None, failure=None, bad_json=False):
        self.requests = []
        self.failure = failure
        self.bad_json = bad_json
        self.draft = draft or {
            "status": "found",
            "answer": "Delivery within 45 days of award.",
            "source_chunk_ids": ["chunk-1"],
        }

    def complete(self, messages, tools=None, **kwargs):
        assert tools is None, "Specialists must not ask the model to select tools"
        self.requests.append((messages, kwargs))
        if self.failure:
            raise self.failure
        draft = self.draft.copy()
        if kwargs["response_format"]["json_schema"]["name"] == "answer_or_search":
            draft.update(action="answer", search_queries=[], missing_information=[])
        content = json.dumps(draft)
        if self.bad_json:
            content = "not JSON"
        return {
            "message": {"role": "assistant", "content": content},
            "usage": {"total_tokens": 20},
            "finish_reason": "stop",
        }


class FakeSearch:
    def __init__(self, empty=False, failure=None):
        self.empty = empty
        self.failure = failure
        self.arguments = []

    def run(self, arguments):
        self.arguments.append(arguments)
        if self.failure:
            raise self.failure
        if self.empty:
            return []
        return [
            {
                "chunk_id": "chunk-1",
                "file_name": "rfp.pdf",
                "page_number": 2,
                "section": None,
                "text": "Delivery within 45 days of award.",
            }
        ]


def test_direct_search_then_one_model_call():
    model, search = FakeModel(), FakeSearch()
    result = answer_question("When is delivery?", model, {"search_documents": search})
    assert result.status == "found"
    assert result.sources[0]["page_number"] == 2
    assert search.arguments == [{"query": "When is delivery?", "top_k": 5}]
    assert len(model.requests) == 1
    assert "45 days" in model.requests[0][0][-1]["content"]
    assert [step["step"] for step in result.trace] == ["retrieve_evidence", "answer_or_search"]


def test_empty_search_can_return_qualified_abstention():
    model = FakeModel(
        draft={"status": "not_found", "answer": "Not found in documents", "source_chunk_ids": []}
    )
    result = answer_question("When?", model, {"search_documents": FakeSearch(empty=True)})
    assert result.status == "not_found"
    assert result.sources == []
    assert len(model.requests) == 1


@pytest.mark.parametrize("ids", [[], ["invented"]])
def test_invalid_citations_are_rejected(ids):
    model = FakeModel(draft={"status": "found", "answer": "45 days", "source_chunk_ids": ids})
    assert answer_question("When?", model, {"search_documents": FakeSearch()}).status == "error"


@pytest.mark.parametrize("failure", [TimeoutError(), RuntimeError()])
def test_search_failure_skips_model(failure):
    model = FakeModel()
    result = answer_question("When?", model, {"search_documents": FakeSearch(failure=failure)})
    assert result.status == "error"
    assert not model.requests


def test_model_timeout_returns_error():
    result = answer_question(
        "When?", FakeModel(failure=TimeoutError()), {"search_documents": FakeSearch()}
    )
    assert result.status == "error"


def test_bad_json_returns_error():
    assert (
        answer_question(
            "When?", FakeModel(bad_json=True), {"search_documents": FakeSearch()}
        ).status
        == "error"
    )


def test_missing_search_registration_returns_error():
    model = FakeModel()
    assert answer_question("When?", model, {}).status == "error"
    assert not model.requests


def test_blank_question_is_rejected():
    with pytest.raises(ValueError):
        answer_question(" ", FakeModel(), {})


@pytest.mark.parametrize(
    "explanation",
    [
        "Original: 30 days; Addendum 1 changes it to 45 days. Use 45 days.",
        "The sources state 30 and 45 days. Conflict unresolved.",
    ],
)
def test_both_source_references_survive(explanation):
    class TwoSources(FakeSearch):
        def run(self, arguments):
            original = super().run(arguments)[0]
            return [original, {**original, "chunk_id": "chunk-2", "file_name": "addendum.pdf"}]

    model = FakeModel(
        draft={"status": "found", "answer": explanation, "source_chunk_ids": ["chunk-1", "chunk-2"]}
    )
    result = answer_question("When?", model, {"search_documents": TwoSources()})
    assert result.answer == explanation
    assert len(result.sources) == 2
