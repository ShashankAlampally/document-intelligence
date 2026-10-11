"""Verify grouped extraction using the real graphs without external API calls."""

import json

import pytest

pytest.importorskip("langgraph")

from test_extraction_agent import FakeModel, FakeSearch

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from app.agents.extraction.graph.workflow import extract_field_group
from app.agents.extraction.models.field_catalog import FIELD_GROUPS, FIELD_GUIDANCE, FIELD_NAMES


class GroupModel(FakeModel):
    def complete(self, messages, tools=None, **kwargs):
        if not tools and kwargs["response_format"]["json_schema"]["name"] == "bid_fields":
            names = []
            for line in messages[0]["content"].splitlines():
                if line.startswith("- "):
                    names.append(line[2:].split(":", 1)[0])
            self.fields = [
                {
                    "name": name,
                    "value": f"Test value for {name}",
                    "source_chunk_ids": ["evidence-1"],
                    "confidence": 0.8,
                    "notes": None,
                }
                for name in names
            ]
        return super().complete(messages, tools=tools, **kwargs)


def test_all_twenty_fields_use_seven_independent_graph_runs():
    model, tool = GroupModel(), FakeSearch()
    result = extract_bid_fields(model, {"search_documents": tool})
    assert result.status == "completed"
    assert len(result.fields) == 20
    assert set(result.fields) == set(FIELD_NAMES)
    assert len(tool.calls) == 33
    assert {step["field_group"] for step in result.trace if "field_group" in step} == set(
        FIELD_GROUPS
    )
    for field in result.fields.values():
        assert field.sources[0]["chunk_id"] == "evidence-1"
    output_calls = [
        call
        for call in model.calls
        if call[1]["response_format"]["json_schema"]["name"] == "bid_fields"
    ]
    assert len(output_calls) == 7
    assert len(model.calls) == 8
    assert len(result.validation_report[0]["fields"]) == 20
    assert all(call["top_k"] == 5 for call in tool.calls)
    assert [messages[0]["content"].count("\n- ") for messages, _ in output_calls] == [3] * 6 + [2]
    for messages, _ in output_calls:
        assert len(json.loads(messages[1]["content"])) == 1


def test_failure_keeps_prior_results_in_trace_record_and_stops():
    class FailingModel(GroupModel):
        def complete(self, messages, tools=None, **kwargs):
            if "Term of Bid:" in messages[0]["content"]:
                raise TimeoutError("Test timeout")
            return super().complete(messages, tools=tools, **kwargs)

    tool = FakeSearch()
    result = extract_bid_fields(FailingModel(), {"search_documents": tool})
    assert result.status == "error"
    assert "contract_requirements" in result.error
    assert "TimeoutError" in result.error
    assert set(result.fields) == set(FIELD_GROUPS["bid_details"])
    assert len(tool.calls) == 6
    assert result.trace[-1]["field_group"] == "contract_requirements"


def test_one_group_returns_only_its_requested_fields():
    names = FIELD_GROUPS["delivery_and_documents"]
    result = extract_field_group(GroupModel(), {"search_documents": FakeSearch()}, names)
    assert result.status == "completed"
    assert set(result.fields) == set(names)


def test_empty_search_still_emits_all_twenty_null_fields():
    result = extract_bid_fields(GroupModel(), {"search_documents": FakeSearch(empty=True)})
    assert result.status == "completed"
    assert len(result.fields) == 20
    assert all(field.value is None for field in result.fields.values())


@pytest.mark.parametrize("names", [[], ["unknown"], ["Title", "Title"]])
def test_invalid_group_is_rejected_before_model_calls(names):
    model = GroupModel()
    with pytest.raises(ValueError):
        extract_field_group(model, {}, names)
    assert not model.calls


def test_fields_from_another_group_are_rejected():
    result = extract_field_group(
        FakeModel(), {"search_documents": FakeSearch()}, FIELD_GROUPS["products"]
    )
    assert result.status == "error"
    assert not result.fields


def test_catalog_has_twenty_unique_fields_with_instructions():
    assert len(FIELD_NAMES) == len(set(FIELD_NAMES)) == 20
    assert set(FIELD_GUIDANCE) == set(FIELD_NAMES)


def test_truncated_json_returns_actionable_error_and_usage():
    class TruncatedModel(GroupModel):
        def complete(self, messages, tools=None, **kwargs):
            response = super().complete(messages, tools=tools, **kwargs)
            if not tools:
                response["finish_reason"] = "length"
            return response

    result = extract_field_group(
        TruncatedModel(), {"search_documents": FakeSearch()}, FIELD_GROUPS["products"]
    )
    assert result.status == "error"
    assert "RFP_LLM_MAX_TOKENS" in result.error
    assert result.trace[-1]["finish_reason"] == "length"
    assert result.trace[-1]["usage"] == {"total_tokens": 20}


def test_three_fields_can_send_fifteen_distinct_chunks_within_budget():
    class FiveChunksSearch(FakeSearch):
        def run(self, arguments):
            passage = super().run(arguments)[0]
            prefix = len(self.calls)
            return [
                {
                    **passage,
                    "text": f"Independent evidence for field {prefix}, rank {rank}.",
                    "chunk_id": "evidence-1"
                    if prefix == 1 and rank == 0
                    else f"evidence-{prefix}-{rank}",
                }
                for rank in range(arguments["top_k"])
            ]

    model = GroupModel()
    result = extract_field_group(
        model, {"search_documents": FiveChunksSearch()}, FIELD_GROUPS["bid_details"]
    )
    assert result.status == "completed"
    evidence = json.loads(model.calls[0][0][1]["content"])
    assert len(evidence) == 15
    assert result.trace[0]["selection"]["max_chunks"] == 15
    assert result.trace[0]["selection"]["serialized_chars"] <= 12000
