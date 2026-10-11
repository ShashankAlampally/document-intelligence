"""Exercise the real validation loop with scripted responses, never Groq."""

import json

import pytest
from test_extraction_agent import FIELD_NAMES, FakeModel, FakeSearch

from app.agents.extraction.graph.workflow import extract_field_group


class ReviewingModel(FakeModel):
    def __init__(self, decision="needs_evidence", persistent=False, malformed=False):
        super().__init__()
        self.decision = decision
        self.persistent = persistent
        self.malformed = malformed
        self.reviews = 0
        self.extractions = []

    def complete(self, messages, tools=None, **kwargs):
        schema = kwargs["response_format"]["json_schema"]
        if schema["name"] != "field_validation":
            names = schema["schema"]["$defs"]["FieldDraft"]["properties"]["name"]["enum"]
            self.extractions.append(names)
            self.fields = [field for field in self.fields if field["name"] in names]
            if len(names) == 1:
                self.fields[0]["value"] = "Corrected delivery"
            return super().complete(messages, tools, **kwargs)
        self.calls.append((messages, kwargs))
        self.reviews += 1
        fields = json.loads(messages[1]["content"])["fields"]
        decisions = [
            {
                "name": field["name"],
                "decision": self.decision
                if field["name"] == "Delivery Date" and (self.reviews == 1 or self.persistent)
                else "accepted",
                "reason": "Check delivery evidence",
            }
            for field in fields
        ]
        if self.malformed:
            decisions = decisions + decisions[:1]
        return {
            "message": {"content": json.dumps({"fields": decisions})},
            "usage": {"total_tokens": 2},
            "finish_reason": "stop",
        }


@pytest.mark.parametrize("decision,searches", [("needs_evidence", 4), ("incorrect", 3)])
def test_only_rejected_field_is_corrected(decision, searches):
    model, tool = ReviewingModel(decision), FakeSearch()
    result = extract_field_group(model, {"search_documents": tool}, FIELD_NAMES)
    assert result.status == "completed"
    assert len(tool.calls) == searches
    if decision == "needs_evidence":
        assert tool.calls[-1]["field_name"] == "Delivery Date"
    assert model.extractions == [FIELD_NAMES, ["Delivery Date"]]
    assert result.fields["Bid Number"].value == "X-1"
    assert result.fields["Title"].value == "Laptop purchase"
    assert result.fields["Delivery Date"].value == "Corrected delivery"
    assert model.reviews == 2
    assert len(result.validation_report[0]["fields"]) == 3
    assert len(model.calls) == 4
    assert "Check delivery evidence" in model.calls[2][0][-1]["content"]


def test_persistent_rejection_stops_and_returns_unresolved():
    model, tool = ReviewingModel(persistent=True), FakeSearch()
    result = extract_field_group(model, {"search_documents": tool}, FIELD_NAMES)
    field = result.fields["Delivery Date"]
    assert result.status == "completed"
    assert model.reviews == 2
    assert field.value is None and field.confidence == 0
    assert "Unresolved after validation retry" in field.notes
    assert result.fields["Bid Number"].value == "X-1"
    assert len(tool.calls) == 4


def test_invalid_validator_report_fails_closed():
    result = extract_field_group(
        ReviewingModel(malformed=True), {"search_documents": FakeSearch()}, FIELD_NAMES
    )
    assert result.status == "error"
    assert "validation failed" in result.error
    assert not result.fields


def test_empty_evidence_retries_once_without_model_calls():
    model, tool = FakeModel(), FakeSearch(empty=True)
    result = extract_field_group(model, {"search_documents": tool}, FIELD_NAMES)
    assert result.status == "completed"
    assert len(tool.calls) == 6
    assert not model.calls
    assert all(field.value is None for field in result.fields.values())
    assert all("Unresolved" in field.notes for field in result.fields.values())


def test_search_failure_during_retry_stops():
    class FailingSearch(FakeSearch):
        def run(self, arguments):
            if len(self.calls) == 3:
                raise TimeoutError("retry search failed")
            return super().run(arguments)

    result = extract_field_group(
        ReviewingModel(), {"search_documents": FailingSearch()}, FIELD_NAMES
    )
    assert result.status == "error"
    assert "Search failed" in result.error


def test_new_retry_evidence_preserves_accepted_original_sources():
    class NewEvidenceSearch(FakeSearch):
        def run(self, arguments):
            found = super().run(arguments)
            if len(self.calls) > 3:
                found[0]["chunk_id"] = "new-evidence"
                found[0]["text"] = "Corrected delivery after award."
            return found

    result = extract_field_group(
        ReviewingModel(), {"search_documents": NewEvidenceSearch()}, FIELD_NAMES
    )
    assert result.status == "completed"
    assert result.fields["Bid Number"].sources[0]["chunk_id"] == "evidence-1"
    assert result.fields["Delivery Date"].sources[0]["chunk_id"] == "evidence-1"
    assert len(result.validation_report) == 1
    assert result.validation_report[0]["correction_attempts"] == 1


@pytest.mark.parametrize("failure", ["timeout", "truncated", "unknown_field", "blank_reason"])
def test_validator_provider_and_contract_failures_are_explicit(failure):
    class BrokenValidator(FakeModel):
        def complete(self, messages, tools=None, **kwargs):
            response = super().complete(messages, tools, **kwargs)
            if kwargs["response_format"]["json_schema"]["name"] == "field_validation":
                if failure == "timeout":
                    raise TimeoutError("offline timeout")
                if failure == "truncated":
                    response["finish_reason"] = "length"
                else:
                    report = json.loads(response["message"]["content"])
                    key = "name" if failure == "unknown_field" else "reason"
                    report["fields"][0][key] = "unknown field" if key == "name" else " "
                    response["message"]["content"] = json.dumps(report)
            return response

    result = extract_field_group(BrokenValidator(), {"search_documents": FakeSearch()}, FIELD_NAMES)
    assert result.status == "error"
    assert result.trace[-1]["step"] == "validate_fields"
    assert result.trace[-1]["error_detail"]


def test_correction_evidence_stays_within_configured_budget():
    class LotsOfEvidence(FakeSearch):
        def run(self, arguments):
            found = super().run(arguments)[0]
            if len(self.calls) <= 3:
                return [found]
            return [
                {
                    **found,
                    "chunk_id": f"new-{rank}",
                    "text": f"Delivery evidence {rank}: " + "x" * 1900,
                }
                for rank in range(5)
            ]

    model = ReviewingModel()
    result = extract_field_group(model, {"search_documents": LotsOfEvidence()}, FIELD_NAMES)
    assert result.status == "completed"
    # Correction call includes validation feedback after the evidence message.
    evidence = json.loads(model.calls[2][0][1]["content"])
    assert len(evidence) <= 15
    assert len(json.dumps(evidence, ensure_ascii=False)) <= 12000
    review_evidence = json.loads(model.calls[3][0][1]["content"])["evidence"]
    assert {item["chunk_id"] for item in review_evidence} == {"evidence-1"}
    assert review_evidence[0] in evidence
