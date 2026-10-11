"""Cross-upload retrieval, citations and parent routing without network calls."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.tools.document_search import SearchTool


def test_search_balances_uploads_and_preserves_identity(monkeypatch):
    first, second, excluded = uuid4(), uuid4(), uuid4()
    calls = []

    def search(query, provider, store, top_k, filters, **kwargs):
        calls.append((filters.discovery_id, top_k))
        assert filters.discovery_id != excluded
        source = SimpleNamespace(
            discovery_id=filters.discovery_id,
            folder_name="Bid1" if filters.discovery_id == first else "Bid2",
            file_name="rfp.pdf",
            doc_type="rfp",
            addendum_number=None,
            document_date=None,
        )
        chunk = SimpleNamespace(
            chunk_id=filters.discovery_id,
            source=source,
            page_number=2,
            section=None,
            text="Warranty: 1 year" if filters.discovery_id == first else "Warranty: 3 years",
        )
        return [SimpleNamespace(chunk=chunk, similarity=0.7)]

    monkeypatch.setattr("app.tools.document_search.search_documents", search)
    tool = SearchTool(None, None, [first, second, first])
    monkeypatch.setattr(tool, "add_heading_context", lambda evidence: evidence)
    monkeypatch.setattr(tool, "qa_supporting_passages", lambda evidence: [])
    evidence = tool.run({"query": "Compare warranties", "top_k": 2})
    assert calls == [(first, 2), (second, 2)]
    assert [item["folder_name"] for item in evidence] == ["Bid1", "Bid2"]
    assert [item["discovery_id"] for item in evidence] == [str(first), str(second)]

    from test_question_answer_graph import FakeModel

    from app.agents.qa.graph.workflow import answer_question

    result = answer_question(
        "Compare warranties",
        FakeModel(
            draft={
                "status": "found",
                "answer": "Bid1: 1 year. Bid2: 3 years.",
                "source_chunk_ids": [str(first), str(second)],
            }
        ),
        {"search_documents": tool},
    )
    assert result.status == "found"
    assert len(result.sources) == 2
    assert result.sources[1]["folder_name"] == "Bid2"


def test_empty_selection_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        SearchTool(None, None, [])


def test_parent_does_not_merge_twenty_fields_across_uploads():
    from test_extraction_agent import FakeSearch
    from test_main_graph import MainModel

    from app.agents.planner.graph.workflow import run_request

    model, tool = MainModel("extraction"), FakeSearch()
    result = run_request(
        "Extract all fields", [uuid4(), uuid4()], model, {"search_documents": tool}
    )
    assert result.extraction_result is None
    assert "Select one folder" in result.qa_result.answer
    assert len(model.calls) == 1
    assert not tool.calls


def test_parent_rejects_mismatched_search_selection():
    from test_main_graph import MainModel

    from app.agents.planner.graph.workflow import run_request

    with pytest.raises(ValueError, match="must match"):
        run_request(
            "Deadline?", uuid4(), MainModel(), {"search_documents": SearchTool(None, None, uuid4())}
        )
