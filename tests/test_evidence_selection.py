"""Check field coverage and bounded, intact evidence without model calls."""

import json

import pytest

from app.agents.extraction.models.field_catalog import FIELD_NAMES
from app.agents.extraction.prompts.search_queries import FIELD_SEARCH_QUERIES
from app.agents.shared.retrieve_evidence import retrieve_evidence
from app.agents.shared.select_evidence import select_evidence
from app.agents.shared.state import ToolState


def chunk(name, text="Evidence", **metadata):
    return {"chunk_id": name, "text": text, **metadata}


def test_budget_balances_searches_instead_of_filling_from_first_field():
    results = [
        [chunk("contact-1"), chunk("contact-2"), chunk("contact-3")],
        [chunk("quantity-1"), chunk("quantity-2")],
        [chunk("forms-1")],
    ]
    selected = select_evidence(results, max_chunks=3)
    assert [item["chunk_id"] for item in selected] == ["contact-1", "quantity-1", "forms-1"]


def test_duplicates_do_not_use_another_slot_or_repeat_in_context():
    shared = chunk("shared", page_number=2)
    selected = select_evidence([[shared, chunk("second")], [shared, chunk("third")]], max_chunks=3)
    assert [item["chunk_id"] for item in selected] == ["shared", "second", "third"]
    assert selected[0] is shared


def test_character_budget_includes_metadata_and_json_separators():
    first = chunk("first", "日本語", file_name="A long source file name.pdf", page_number=5)
    second = chunk("second")
    exact_limit = len(json.dumps([first, second], ensure_ascii=False))
    assert select_evidence([[first], [second]], max_chars=exact_limit) == [first, second]
    assert select_evidence([[first], [second]], max_chars=exact_limit - 1) == [first]


def test_oversized_chunk_is_skipped_without_trimming_or_blocking_later_results():
    large = chunk("large", "x" * 1000)
    small = chunk("small", "Complete cited passage.", page_number=3)
    original = dict(large)
    assert select_evidence([[large, small]], max_chars=200) == [small]
    assert large == original


@pytest.mark.parametrize("results", [[], [[]], [[], []]])
def test_empty_searches_have_empty_evidence(results):
    assert select_evidence(results, max_chunks=12, max_chars=12000) == []


def test_unbounded_defaults_keep_all_unique_passages():
    results = [[chunk("first", "x" * 13000)], [chunk("second")]]
    assert len(select_evidence(results)) == 2
    assert ToolState().max_evidence_chars is None


def test_trace_exposes_evidence_dropped_by_budget():
    class Search:
        def run(self, arguments):
            return [chunk(arguments["query"], "x" * 1000)]

    state = ToolState(search_queries=["contacts", "products"], max_evidence_chars=200)
    result = retrieve_evidence(state, {"search_documents": Search()})
    assert result["evidence"] == []
    selection = result["trace"][0]["selection"]
    assert selection["candidate_count"] == 2
    assert selection["selected_count"] == 0
    assert selection["queries_without_selected_evidence"] == ["contacts", "products"]


def test_every_assignment_field_has_a_distinct_focused_query():
    assert set(FIELD_SEARCH_QUERIES) == set(FIELD_NAMES)
    assert len(set(FIELD_SEARCH_QUERIES.values())) == 20
