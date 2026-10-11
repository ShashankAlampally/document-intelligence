"""Run the real extraction graph with predictable model/tool responses."""

import json

import pytest

pytest.importorskip("langgraph")

from app.agents.extraction.graph.workflow import extract_field_group

FIELD_NAMES = ["Bid Number", "Title", "Delivery Date"]


def extract_bid_fields(model, tools):
    return extract_field_group(model, tools, FIELD_NAMES)


class FakeSearch:
    returns_document_evidence = True
    definition = {"type": "function", "function": {"name": "search_documents"}}

    def __init__(self, empty=False):
        self.empty = empty
        self.calls = []

    def run(self, arguments):
        self.calls.append(arguments)
        if self.empty:
            return []
        return [
            {
                "chunk_id": "evidence-1",
                "file_name": "rfp.pdf",
                "page_number": 1,
                "section": None,
                "text": "RFP X-1. Laptop purchase. Deliver within 45 days.",
            }
        ]


class FakeModel:
    def __init__(self, fields=None, direct=False, bad_json=False):
        self.calls = []
        self.direct = direct
        self.bad_json = bad_json
        if fields is None:
            fields = [
                {
                    "name": name,
                    "value": value,
                    "source_chunk_ids": ["evidence-1"],
                    "confidence": 0.8,
                    "notes": None,
                }
                for name, value in zip(FIELD_NAMES, ["X-1", "Laptop purchase", "Within 45 days"])
            ]
        self.fields = fields

    def complete(self, messages, tools=None, **kwargs):
        self.calls.append((messages, kwargs))
        assert tools is None, "Specialists must not ask the model to select tools"
        if kwargs["response_format"]["json_schema"]["name"] == "field_validation":
            fields = json.loads(messages[1]["content"])["fields"]
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "fields": [
                                {
                                    "name": field["name"],
                                    "decision": "accepted",
                                    "reason": "Scripted support",
                                }
                                for field in fields
                            ]
                        }
                    )
                },
                "usage": {},
                "finish_reason": "stop",
            }
        content = json.dumps({"fields": self.fields})
        if self.bad_json:
            content = "not JSON"
        message = {"role": "assistant", "content": content}
        return {"message": message, "usage": {"total_tokens": 20}, "finish_reason": "stop"}


def test_extraction_reuses_tool_loop_and_resolves_sources():
    model, tool = FakeModel(), FakeSearch()
    result = extract_bid_fields(model, {"search_documents": tool})
    assert result.status == "completed"
    assert set(result.fields) == set(FIELD_NAMES)
    assert result.fields["Delivery Date"].value == "Within 45 days"
    assert result.fields["Bid Number"].sources[0]["file"] == "rfp.pdf"
    assert result.fields["Bid Number"].sources[0]["page"] == 1
    assert len(tool.calls) == 3
    assert len(model.calls) == 2
    assert [step["step"] for step in result.trace] == [
        "retrieve_evidence",
        "extract_fields",
        "validate_fields",
    ]


def test_empty_retrieval_returns_all_fields_as_missing():
    model = FakeModel()
    result = extract_bid_fields(model, {"search_documents": FakeSearch(empty=True)})
    assert result.status == "completed"
    assert len(model.calls) == 0
    for field in result.fields.values():
        assert field.value is None
        assert field.sources == []
        assert field.confidence == 0
        assert "No evidence retrieved" in field.notes


def test_response_schema_limits_citations_to_supplied_evidence():
    model = FakeModel()
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.status == "completed"
    schema = model.calls[0][1]["response_format"]["json_schema"]["schema"]
    properties = schema["$defs"]["FieldDraft"]["properties"]
    assert properties["source_chunk_ids"]["items"]["enum"] == ["evidence-1"]
    assert properties["name"]["enum"] == FIELD_NAMES


def test_invented_citation_is_rejected_with_diagnostic_detail():
    model = FakeModel()
    model.fields[0]["source_chunk_ids"] = ["mixed-up-id"]
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.status == "error"
    assert result.trace[-1]["error_detail"] == "Field cites evidence that was not retrieved"


@pytest.mark.parametrize("problem", ["unknown_source", "no_source", "duplicate", "confidence"])
def test_invalid_field_output_is_rejected(problem):
    model = FakeModel()
    if problem == "unknown_source":
        model.fields[0]["source_chunk_ids"] = ["invented"]
    elif problem == "no_source":
        model.fields[0]["source_chunk_ids"] = []
    elif problem == "duplicate":
        model.fields[1]["name"] = model.fields[0]["name"]
    else:
        model.fields[0]["confidence"] = 2
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.status == "error"
    assert not result.fields


def test_missing_field_is_normalized_without_guessing():
    class MissingModel(FakeModel):
        def complete(self, messages, tools=None, **kwargs):
            if kwargs["response_format"]["json_schema"]["name"] == "bid_fields":
                names = kwargs["response_format"]["json_schema"]["schema"]["$defs"]["FieldDraft"][
                    "properties"
                ]["name"]["enum"]
                self.fields = [field for field in self.fields if field["name"] in names]
            return super().complete(messages, tools, **kwargs)

    model = MissingModel()
    model.fields[2].update(value=None, source_chunk_ids=[], confidence=0.7, notes=None)
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.fields["Delivery Date"].confidence == 0
    assert "Unresolved after validation retry" in result.fields["Delivery Date"].notes


def test_bad_json_returns_error():
    result = extract_bid_fields(FakeModel(bad_json=True), {"search_documents": FakeSearch()})
    assert result.status == "error"


def test_focused_searches_finish_with_unique_evidence():
    class SearchingModel(FakeModel):
        def complete(self, messages, tools=None, **kwargs):
            if tools:
                return super().complete([messages[0]], tools=tools, **kwargs)
            return super().complete(messages, tools=tools, **kwargs)

    model, tool = SearchingModel(), FakeSearch()
    result = extract_bid_fields(model, {"search_documents": tool})
    assert result.status == "completed"
    assert len(tool.calls) == 3
    final_messages = model.calls[0][0]
    assert [message["role"] for message in final_messages] == ["system", "user"]
    assert len(json.loads(final_messages[1]["content"])) == 1


def test_distinct_field_searches_are_combined_into_one_model_call():
    class FieldSearch(FakeSearch):
        def run(self, arguments):
            evidence = super().run(arguments)[0]
            evidence["chunk_id"] = f"field-{len(self.calls)}"
            evidence["text"] = f"Independent supporting evidence for field {len(self.calls)}."
            return [evidence]

    model, tool = FakeModel(), FieldSearch()
    for number, field in enumerate(model.fields, start=1):
        field["source_chunk_ids"] = [f"field-{number}"]
    result = extract_bid_fields(model, {"search_documents": tool})
    assert result.status == "completed"
    queries = [call["query"] for call in tool.calls]
    assert len(set(queries)) == 3
    assert "identifier" in queries[0]
    assert "title" in queries[1]
    assert "delivery" in queries[2]
    assert len(model.calls) == 2
    evidence = json.loads(model.calls[0][0][1]["content"])
    assert {item["chunk_id"] for item in evidence} == {"field-1", "field-2", "field-3"}
    assert len(model.calls[0][0][1]["content"]) <= 12000
    assert result.trace[0]["selection"]["queries_without_selected_evidence"] == []


class TwoSourceSearch(FakeSearch):
    def run(self, arguments):
        original = super().run(arguments)[0]
        original["text"] = "RFP X-1. Laptop purchase. Deliver within 30 days."
        return [
            original,
            {
                **original,
                "chunk_id": "evidence-2",
                "file_name": "Addendum 1.pdf",
                "doc_type": "addendum",
                "addendum_number": 1,
                "text": "Delivery is changed from 30 to 45 days after award.",
            },
        ]


@pytest.mark.parametrize("unresolved", [False, True])
def test_changed_or_unresolved_field_preserves_notes_and_both_sources(unresolved):
    # Scripted output checks result handling, not the model's reasoning accuracy.
    model = FakeModel()
    field = model.fields[2]
    field.update(
        source_chunk_ids=["evidence-1", "evidence-2"],
        notes="Original rfp.pdf page 1: 30 days; Addendum 1.pdf page 1: 45 days.",
    )
    if unresolved:
        field["value"] = None
        field["notes"] += " Conflict unresolved; precedence cannot be established."
    result = extract_bid_fields(model, {"search_documents": TwoSourceSearch()})
    assert result.status == "completed"
    output = result.fields["Delivery Date"]
    assert output.value == field["value"]
    assert output.notes == field["notes"]
    assert [item["chunk_id"] for item in output.sources] == ["evidence-1", "evidence-2"]
    assert output.sources[1]["addendum_number"] == 1
    if unresolved:
        assert output.confidence == 0


@pytest.mark.parametrize("notes", [None, "", "   "])
def test_cited_null_requires_explanation(notes):
    model = FakeModel()
    model.fields[2].update(value=None, notes=notes)
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.status == "error"


def test_cited_null_cannot_use_invented_source():
    model = FakeModel()
    model.fields[2].update(
        value=None, source_chunk_ids=["invented"], notes="Unresolved conflicting delivery values."
    )
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.status == "error"
