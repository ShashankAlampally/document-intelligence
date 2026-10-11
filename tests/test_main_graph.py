"""Run the real parent/child graphs with scripted models, without Groq calls."""

import json
from uuid import uuid4

import pytest

pytest.importorskip("langgraph")
from test_extraction_agent import FakeSearch
from test_extraction_groups import GroupModel
from test_question_answer_graph import FakeModel as QaModel

from app.agents.planner.graph.workflow import run_request


class MainModel:
    def __init__(self, task="qa", failure=False, bad_json=False, child_failure=False):
        self.task = task
        self.failure = failure
        self.bad_json = bad_json
        self.child_failure = child_failure
        self.calls = []
        self.extraction = GroupModel()
        self.qa = QaModel(
            draft={
                "status": "found",
                "answer": "Within 45 days.",
                "source_chunk_ids": ["evidence-1"],
            }
        )

    def complete(self, messages, tools=None, **kwargs):
        assert tools is None
        self.calls.append(messages)
        schema_name = kwargs["response_format"]["json_schema"]["name"]
        if schema_name == "workflow_choice":
            if self.failure:
                raise TimeoutError()
            content = json.dumps({"task": self.task, "message": None})
            if self.task == "reply":
                content = json.dumps({"task": "reply", "message": "Hello!"})
            if self.bad_json:
                content = "not JSON"
            return {"message": {"content": content}, "usage": {}, "finish_reason": "stop"}
        if self.child_failure:
            raise TimeoutError()
        if schema_name in {"bid_fields", "field_validation"}:
            return self.extraction.complete(messages, **kwargs)
        return self.qa.complete(messages, **kwargs)


@pytest.mark.parametrize(
    "task,calls,searches", [("qa", 2, 1), ("extraction", 9, 33), ("reply", 1, 0)]
)
def test_main_graph_routes_to_one_workflow(task, calls, searches):
    model, tool = MainModel(task), FakeSearch()
    upload_id = uuid4()
    result = run_request("User request", upload_id, model, {"search_documents": tool})
    assert not result.error
    assert result.discovery_id == upload_id
    assert result.choice.task == task
    assert len(model.calls) == calls
    assert len(tool.calls) == searches
    assert result.trace[0]["step"] == "choose_workflow"
    if task == "extraction":
        assert len(result.extraction_result.fields) == 20
        assert result.qa_result is None
    else:
        assert result.qa_result is not None
        assert result.extraction_result is None


@pytest.mark.parametrize("values", [{"failure": True}, {"bad_json": True}, {"task": "unknown"}])
def test_bad_routing_stops_before_search(values):
    tool = FakeSearch()
    result = run_request("Question", uuid4(), MainModel(**values), {"search_documents": tool})
    assert result.error
    assert not tool.calls


@pytest.mark.parametrize("task", ["qa", "extraction"])
def test_child_error_is_returned_by_parent(task):
    result = run_request(
        "Request", uuid4(), MainModel(task, child_failure=True), {"search_documents": FakeSearch()}
    )
    assert result.error
    assert "TimeoutError" in result.error


def test_blank_request_is_rejected():
    with pytest.raises(ValueError):
        run_request(" ", uuid4(), MainModel(), {})
