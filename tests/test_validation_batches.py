"""Bound validator input without silently losing any cited passage or field."""

import json

import pytest
from test_extraction_groups import GroupModel

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.models.field_catalog import FIELD_NAMES
from app.agents.extraction.models.fields import ExtractionDraft, FieldDraft
from app.agents.extraction.models.validation_batches import validation_batches
from app.agents.extraction.nodes.validate_fields import validate_fields


def field(name, ids):
    return FieldDraft(
        name=name, value="Supported value", source_chunk_ids=ids, confidence=0.8, notes=None
    )


def passage(identity, size=100):
    return {
        "chunk_id": identity,
        "file_name": "rfp.pdf",
        "page_number": 1,
        "section": None,
        "text": identity + "x" * size,
    }


def test_unique_citations_are_deduplicated_and_uncited_evidence_excluded():
    fields = [field("Title", ["one"]), field("Bid Number", ["one"])]
    batches = validation_batches(fields, [passage("one"), passage("uncited", 20000)])
    assert len(batches) == 1
    assert [item["chunk_id"] for item in batches[0]["evidence"]] == ["one"]
    assert len(batches[0]["fields"]) == 2


def test_large_validation_splits_fields_and_retains_every_cited_passage():
    evidence = [passage(str(index), 5000) for index in range(4)]
    fields = [field(name, [str(index)]) for index, name in enumerate(FIELD_NAMES[:4])]
    batches = validation_batches(fields, evidence)
    assert len(batches) == 2
    assert [item["name"] for batch in batches for item in batch["fields"]] == FIELD_NAMES[:4]
    assert {item["chunk_id"] for batch in batches for item in batch["evidence"]} == {
        "0",
        "1",
        "2",
        "3",
    }
    assert all(len(json.dumps(batch, ensure_ascii=False)) <= 12000 for batch in batches)
    state = ExtractionState(
        requested_fields=FIELD_NAMES[:4], evidence=evidence, draft=ExtractionDraft(fields=fields)
    )
    model = GroupModel()
    result = validate_fields(state, model)
    assert len(model.calls) == 2
    assert len(result["validation"].fields) == 4
    assert [step["batch_index"] for step in result["trace"]] == [1, 2]
    assert all(step["batch_count"] == 2 for step in result["trace"])


def test_chunk_count_also_splits_batches_without_dropping_citations():
    evidence = [passage(str(index)) for index in range(16)]
    fields = [field(name, [str(index)]) for index, name in enumerate(FIELD_NAMES[:16])]
    batches = validation_batches(fields, evidence)
    assert len(batches) == 2
    assert sum(len(batch["evidence"]) for batch in batches) == 16
    assert all(len(batch["evidence"]) <= 15 for batch in batches)


@pytest.mark.parametrize("problem", ["missing_citation", "oversized_field"])
def test_impossible_validation_fails_explicitly_without_a_model_call(problem):
    evidence = [] if problem == "missing_citation" else [passage("one", 13000)]
    state = ExtractionState(
        requested_fields=["Title"],
        evidence=evidence,
        draft=ExtractionDraft(fields=[field("Title", ["one"])]),
    )
    model = GroupModel()
    result = validate_fields(state, model)
    assert result["error"]
    assert not model.calls
    assert result["trace"][-1]["error_detail"]


def test_field_overhead_can_exceed_evidence_limit_without_dropping_evidence():
    from app.agents.extraction.models.validation_batches import VALIDATION_MAX_CHARS

    draft = field("Bid Summary", ["one"])
    draft.value = "s" * 1100
    evidence = [passage("one", 11200)]
    batches = validation_batches([draft], evidence)
    assert len(batches) == 1
    assert len(json.dumps(batches[0], ensure_ascii=False)) > 12000
    assert len(json.dumps(batches[0], ensure_ascii=False)) <= VALIDATION_MAX_CHARS
    assert batches[0]["evidence"] == evidence


def test_evidence_limit_still_applies_with_larger_payload_allowance():
    with pytest.raises(ValueError, match="exceeds the budget"):
        validation_batches([field("Title", ["one"])], [passage("one", 12500)])


def test_individual_field_also_respects_total_payload_limit():
    draft = field("Bid Summary", ["one"])
    draft.value = "s" * 6000
    with pytest.raises(ValueError, match="exceeds the budget"):
        validation_batches([draft], [passage("one", 11000)])
