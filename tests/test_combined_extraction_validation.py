"""Verify combined validation and field-only correction through real graphs."""

import json
from collections import Counter

from test_extraction_agent import FakeSearch
from test_extraction_groups import GroupModel

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from app.agents.extraction.models.field_catalog import FIELD_GROUPS, FIELD_NAMES


class CombinedModel(GroupModel):
    def __init__(self, rejected=None, persistent=False):
        super().__init__()
        self.rejected = rejected or {}
        self.persistent = persistent
        self.reviewed = Counter()
        self.extractions = []

    def complete(self, messages, tools=None, **kwargs):
        schema = kwargs["response_format"]["json_schema"]
        if schema["name"] == "bid_fields":
            names = schema["schema"]["$defs"]["FieldDraft"]["properties"]["name"]["enum"]
            self.extractions.append(names)
            return super().complete(messages, tools, **kwargs)
        self.calls.append((messages, kwargs))
        fields = json.loads(messages[1]["content"])["fields"]
        decisions = []
        for field in fields:
            name = field["name"]
            decision = "accepted"
            if name in self.rejected and (not self.reviewed[name] or self.persistent):
                decision = self.rejected[name]
            decisions.append({"name": name, "decision": decision, "reason": "Check this field"})
            self.reviewed[name] += 1
        return {
            "message": {"content": json.dumps({"fields": decisions})},
            "finish_reason": "stop",
            "usage": {"total_tokens": 10},
        }


def test_all_groups_are_extracted_before_one_combined_validation():
    model = CombinedModel()
    result = extract_bid_fields(model, {"search_documents": FakeSearch()})
    assert result.status == "completed"
    schemas = [kwargs["response_format"]["json_schema"]["name"] for _, kwargs in model.calls]
    assert schemas == ["bid_fields"] * 7 + ["field_validation"]
    payload = json.loads(model.calls[-1][0][1]["content"])
    assert len(payload["fields"]) == 20
    assert len(payload["evidence"]) == 1
    assert len(result.validation_report[0]["fields"]) == 20
    assert len([step for step in result.trace if step["step"] == "validate_fields"]) == 1


def test_rejections_in_different_groups_only_retry_the_rejected_fields():
    model = CombinedModel({"Delivery Date": "needs_evidence", "Payment Terms": "incorrect"})
    tool = FakeSearch()
    result = extract_bid_fields(model, {"search_documents": tool})
    assert result.status == "completed"
    assert model.extractions[7:] == [["Delivery Date"], ["Payment Terms"]]
    assert len(tool.calls) == 34
    assert tool.calls[-1]["field_name"] == "Delivery Date"
    assert model.reviewed["Title"] == 1
    assert model.reviewed["Payment Terms"] == model.reviewed["Delivery Date"] == 2
    assert result.fields["Title"].value == "Test value for Title"
    assert result.fields["Title"].sources[0]["chunk_id"] == "evidence-1"
    assert len(result.validation_report[0]["fields"]) == 20
    assert len(model.calls) == 11  # 7 extraction + 1 review + 2 correction + 1 review.


def test_every_field_rejected_still_uses_small_bounded_correction_groups():
    model = CombinedModel({name: "incorrect" for name in FIELD_NAMES}, persistent=True)
    tool = FakeSearch()
    result = extract_bid_fields(model, {"search_documents": tool})
    assert result.status == "completed"
    assert model.extractions[7:] == list(FIELD_GROUPS.values())
    assert len(model.calls) == 16
    assert len(tool.calls) == 33  # Incorrect interpretation needs no new search.
    assert all(field.value is None for field in result.fields.values())
    assert all(
        "Unresolved after validation retry" in field.notes for field in result.fields.values()
    )
    assert all(model.reviewed[name] == 2 for name in FIELD_NAMES)


def test_group_progress_callback_saves_drafts_before_combined_validation():
    model = CombinedModel()
    saved = []

    def on_group(name, result):
        assert not model.reviewed
        assert result.validation_report == []
        saved.append((name, set(result.fields)))

    result = extract_bid_fields(model, {"search_documents": FakeSearch()}, on_group=on_group)
    assert result.status == "completed"
    assert saved == [(name, set(fields)) for name, fields in FIELD_GROUPS.items()]
