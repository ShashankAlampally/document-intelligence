from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.tools.document_search import SearchTool


def test_tool_scopes_search_and_preserves_citation(monkeypatch):
    upload_id, chunk_id = uuid4(), uuid4()
    calls = []

    def search(query, provider, store, top_k, filters, **kwargs):
        calls.append((query, top_k, filters))
        chunk = SimpleNamespace(
            chunk_id=chunk_id,
            source=SimpleNamespace(
                discovery_id=upload_id,
                folder_name="Bid1",
                file_name="rfp.pdf",
                doc_type="rfp",
                addendum_number=None,
                document_date=None,
            ),
            page_number=2,
            section=None,
            text="Delivery within 45 days of award.",
        )
        return [SimpleNamespace(chunk=chunk, similarity=0.7)]

    monkeypatch.setattr("app.tools.document_search.search_documents", search)
    tool = SearchTool(None, None, upload_id)
    evidence = tool.run({"query": " delivery "})
    assert calls[0][0:2] == ("delivery", 3)
    assert calls[0][2].discovery_id == upload_id
    assert evidence[0]["chunk_id"] == str(chunk_id)
    assert evidence[0]["page_number"] == 2
    assert evidence[0]["text"] == "Delivery within 45 days of award."
    assert tool.definition["function"]["name"] == "search_documents"


@pytest.mark.parametrize(
    "arguments",
    [{"query": " "}, {"query": "x", "top_k": 21}, {"query": "x", "discovery_id": "other"}],
)
def test_tool_rejects_invalid_input_and_upload_override(arguments):
    with pytest.raises(ValidationError):
        SearchTool(None, None, uuid4()).run(arguments)


def test_tool_accepts_addendum_filters_but_keeps_upload_scope(monkeypatch):
    upload_id = uuid4()
    calls = []

    def search(query, provider, store, top_k, filters, **kwargs):
        calls.append(filters)
        return []

    monkeypatch.setattr("app.tools.document_search.search_documents", search)
    tool = SearchTool(None, None, upload_id)
    assert tool.run({"query": "deadline", "doc_type": "addendum", "addendum_number": 2}) == []
    assert calls[0].discovery_id == upload_id
    assert calls[0].doc_type == "addendum"
    assert calls[0].addendum_number == 2
    assert isinstance(calls[0].addendum_number, int)


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "deadline", "doc_type": "invented"},
        {"query": "deadline", "addendum_number": 0},
    ],
)
def test_invalid_document_filters_are_rejected(arguments):
    with pytest.raises(ValidationError):
        SearchTool(None, None, uuid4()).run(arguments)
