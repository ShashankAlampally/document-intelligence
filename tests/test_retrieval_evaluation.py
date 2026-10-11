from scripts.retrieval_evaluation import normalize, relevant, score, summarize

UPLOADS = {"Bid1": "upload-1", "Bid2": "upload-2"}
REF = dict(bid="Bid1", file="addendum.pdf", page=1, anchors=["July 9", "2:00 PM"])
HIT = dict(
    discovery_id="upload-1", file_name="addendum.pdf", page_number=1, text="Due JULY\n9 at 2:00 PM."
)


def test_requires_correct_bid_file_page_and_content():
    assert relevant(HIT, REF, UPLOADS)
    for patch in [
        dict(discovery_id="upload-2"),
        dict(file_name="wrong.pdf"),
        dict(page_number=2),
        dict(text="A deadline is mentioned"),
    ]:
        assert not relevant({**HIT, **patch}, REF, UPLOADS)


def test_recall_counts_evidence_units_not_duplicate_chunks():
    other = {**REF, "anchors": ["June 27"]}
    metrics = score([HIT, HIT], [REF, other], UPLOADS)
    assert metrics["recall"] == 0.5
    assert metrics["reciprocal_rank"] == 1
    assert metrics["passage_ranks"] == [1, None]


def test_rank_and_cutoff():
    irrelevant = {**HIT, "text": "irrelevant"}
    assert score([irrelevant, HIT], [REF], UPLOADS)["reciprocal_rank"] == 0.5
    assert score([irrelevant, HIT], [REF], UPLOADS, k=1)["recall"] == 0
    assert score([], [REF], UPLOADS)["reciprocal_rank"] == 0


def test_html_has_no_invented_page():
    assert relevant({**HIT, "page_number": None}, {**REF, "page": None}, UPLOADS)
    assert not relevant(HIT, {**REF, "page": None}, UPLOADS)


def test_errors_are_reported_separately_from_misses():
    results = [
        dict(configuration="vector", metrics=dict(recall=0.5, reciprocal_rank=1)),
        dict(configuration="vector", error="model unavailable"),
    ]
    rows = summarize(results, ["vector", "hybrid"])
    assert rows[0]["recall"] == 0.5
    assert rows[0]["errors"] == 1
    assert rows[1]["mrr"] is None


def test_numeric_anchors_do_not_match_a_different_quantity():
    ref = {**REF, "anchors": ["30"]}
    assert not relevant({**HIT, "text": "Quantity 300"}, ref, UPLOADS)
    assert relevant({**HIT, "text": "Quantity: 30."}, ref, UPLOADS)


def test_reference_set_covers_both_bids_and_assignment_examples():
    import json
    from pathlib import Path

    dataset = json.loads(Path("evaluation/retrieval/questions.json").read_text())
    questions = dataset["questions"]
    assert len(questions) >= 15
    assert {bid for q in questions for bid in q["bids"]} == {"Bid1", "Bid2"}
    assert len({q["id"] for q in questions}) == len(questions)
    assert any(q["bids"] == ["Bid1", "Bid2"] for q in questions)
    for q in questions:
        for ref in q["expected_passages"] + q.get("supporting_passages", []):
            assert ref["bid"] in q["bids"]
            assert ref["anchors"]
            assert all(
                f" {normalize(anchor)} " in f" {normalize(ref['source_excerpt'])} "
                for anchor in ref["anchors"]
            )
    assert dataset["abstention_checks"][0]["question"].startswith("Is a bid bond required")


def test_alternative_pages_count_as_one_evidence_unit():
    original = {**REF, "evidence_id": "deadline", "page": 2}
    alternative = {**REF, "evidence_id": "deadline"}
    other = {**REF, "evidence_id": "original-date", "anchors": ["June 27"]}
    metrics = score([HIT], [original, alternative, other], UPLOADS)
    assert metrics["expected_passages"] == 2
    assert metrics["recall"] == 0.5
    assert metrics["passage_ranks"] == [1, None]


def test_filename_variants_and_excerpts_do_not_change_judgment():
    ref = {**REF, "file": "Addendum One.pdf", "source_excerpt": "unrelated stored text"}
    hit = {**HIT, "file_name": "Addendum_One.PDF"}
    assert relevant(hit, ref, UPLOADS)
    assert not relevant({**hit, "file_name": "Addendum_Two.pdf"}, ref, UPLOADS)


def test_table_json_newlines_are_readable_evidence():
    import json

    ref = {**REF, "anchors": ["Warranty certificate or Affidavit", "presented upon award"]}
    for cell in [
        "Warranty\ncertificate or\nAffidavit to be\npresented upon\naward",
        "Warranty\\ncertificate or\\nAffidavit to be\\npresented upon\\naward",
    ]:
        text = json.dumps({"headers": [], "rows": [[cell, None]]})
        assert relevant({**HIT, "text": text}, ref, UPLOADS)
    assert normalize(r"A path C:\new") == "a path c new"


def test_only_table_fragments_decode_literal_newlines():
    ref = {**REF, "anchors": ["iSupplier portal"]}
    fragment = r"Register with the\niSupplier portal."
    assert relevant({**HIT, "text": fragment, "content_type": "table"}, ref, UPLOADS)
    assert not relevant({**HIT, "text": fragment, "content_type": "text"}, ref, UPLOADS)
