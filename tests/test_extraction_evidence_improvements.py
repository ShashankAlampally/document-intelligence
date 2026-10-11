"""Regression checks for coverage, deduplication and honest source context."""

from types import SimpleNamespace

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.prompts.retrieval_plan import retrieval_plan
from app.agents.shared.evidence_content import model_evidence
from app.agents.shared.retrieve_evidence import retrieve_evidence
from app.agents.shared.select_evidence import select_evidence
from app.search.heading_context import build_heading_context


def passage(identity, text, **extra):
    return dict(chunk_id=identity, file_name="rfp.pdf", page_number=1, text=text, **extra)


def test_table_and_text_duplicates_release_budget_for_another_category():
    text = passage("text", "Processor Intel i5. Memory 16GB. Storage 512GB.")
    table = passage("table", '{"rows":[["Processor Intel i5.","Memory 16GB.","Storage 512GB."]]}')
    monitor = passage("monitor", "Touch monitors: quantity 5000")
    decisions = []
    selected = select_evidence(
        [[text, table, monitor]], max_chunks=2, deduplicate_content=True, decisions=decisions
    )
    assert [p["chunk_id"] for p in selected] == ["text", "monitor"]
    assert {"chunk_id": "table", "decision": "duplicate_content"} in decisions


def test_matching_original_and_addendum_text_keeps_both_sources():
    original = passage("original", "Delivery in 30 days.")
    addendum = {**original, "chunk_id": "addendum", "file_name": "addendum.pdf"}
    assert len(select_evidence([[original, addendum]], deduplicate_content=True)) == 2


def test_a_different_numeric_requirement_is_not_an_exact_duplicate():
    a = passage("a", "Quantity 5000")
    b = passage("b", "Quantity 10000")
    assert len(select_evidence([[a, b]], deduplicate_content=True)) == 2


def test_broad_searches_do_not_take_all_slots_before_narrow_fields():
    class Search:
        def run(self, request):
            return [passage(request["query"], request["query"])]

    requests = retrieval_plan(["Product", "contact_info", "company_name"])
    state = ExtractionState(
        requested_fields=["Product", "contact_info", "company_name"],
        search_requests=requests,
        max_evidence_chunks=3,
    )
    result = retrieve_evidence(state, {"search_documents": Search()})
    selected = [p["text"] for p in result["evidence"]]
    assert selected == [requests[0]["query"], requests[3]["query"], requests[5]["query"]]
    assert len(result["trace"][0]["search_results"]) == 6


def test_model_context_keeps_citations_but_scores_stay_only_in_trace():
    item = passage("one", "Evidence", rerank_score=2, vector_rank=1, table_id="table")
    compact = model_evidence(item)
    assert compact["chunk_id"] == "one" and compact["table_id"] == "table"
    assert "rerank_score" not in compact and item["rerank_score"] == 2


def test_continuation_context_can_cross_one_page_without_changing_text():
    def stored(identity, page, start, text):
        return SimpleNamespace(
            chunk_id=identity,
            content_type="text",
            page_number=page,
            start_char=start,
            text=text,
            source=SimpleNamespace(file_name="rfp.pdf"),
        )

    chunks = [
        stored("heading", 5, 0, "Staff Desktop Minimum Requirements\nProcessor i7"),
        stored("continuation", 6, 0, "Warranty: 3 years"),
        stored("unrelated", 8, 0, "Submission instructions"),
    ]
    contexts = build_heading_context(chunks)
    assert contexts["continuation"] == {
        "heading": "Staff Desktop Minimum Requirements",
        "heading_page": 5,
    }
    assert "unrelated" not in contexts
    assert chunks[1].text == "Warranty: 3 years"


def test_nearly_identical_passages_with_changed_numbers_are_kept():
    shared = (
        "This passage specifies the device requirements and the applicable delivery conditions. "
    )
    a = passage("a", shared * 3 + "Delivery within 30 days.")
    b = passage("b", shared * 3 + "Delivery within 45 days.")
    assert len(select_evidence([[a, b]], deduplicate_content=True)) == 2


def test_topic_anchor_can_use_an_explicit_continuation_heading():
    from app.search.service import matching_terms

    hit = SimpleNamespace(chunk=SimpleNamespace(chunk_id="one", text="Warranty 3 years"))
    context = {"one": {"heading": "Staff Desktop Minimum Requirements", "heading_page": 5}}
    assert matching_terms([hit], ["staff", "desktop"], context) == [hit]
    assert matching_terms([hit], ["monitor"], context) == []


def test_tracking_report_records_failed_retrieval_without_crashing():
    from scripts.pipeline_report import render_report

    record = dict(
        discovery_id="id",
        status="error",
        trace=[dict(step="retrieve_evidence", field_group="products", error="TimeoutError")],
    )
    assert "retrieval failed" in render_report(record)


def test_repeated_results_preserve_the_first_ranked_occurrence():
    class Search:
        def run(self, request):
            a = passage("a", "First ranked useful evidence")
            b = passage("b", "Second ranked useful evidence")
            if request["query"] == "first":
                return [a, b]
            return [a]

    state = ExtractionState(
        requested_fields=["Product"],
        max_evidence_chunks=2,
        search_requests=[
            dict(query="first", field_name="Product"),
            dict(query="second", field_name="Product"),
        ],
    )
    result = retrieve_evidence(state, {"search_documents": Search()})
    assert [item["chunk_id"] for item in result["evidence"]] == ["a", "b"]
