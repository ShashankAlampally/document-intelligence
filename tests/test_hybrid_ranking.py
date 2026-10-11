"""Weighted votes, keyword matching and configurable overrides without embeddings."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.retrieval import HybridOptions, SearchTuning
from app.search.fusion import fuse_rankings
from app.search.keyword_search import KeywordSearch, tokenize


def chunk(text, chunk_id=None):
    return SimpleNamespace(chunk_id=chunk_id or uuid4(), text=text)


def hit(record):
    # Fusion also accepts minimal test records while preserving the copied hit.
    return SimpleNamespace(
        chunk=record,
        similarity=0.5,
        keyword_score=2,
        retrieval_score=None,
        model_copy=lambda update: SimpleNamespace(
            chunk=record, similarity=0.5, keyword_score=2, **update
        ),
    )


def test_chunk_high_in_both_rankings_outranks_single_method_hit():
    shared, dense_only = chunk("shared"), chunk("dense")
    result = fuse_rankings([hit(dense_only), hit(shared)], [hit(shared)], HybridOptions(), 3)
    assert result[0].chunk is shared
    assert result[0].retrieval_score == pytest.approx(1 / 62 + 1 / 61)
    assert result[0].vector_rank == 2
    assert result[0].keyword_rank == 1


def test_keyword_weight_changes_order_without_comparing_raw_scores():
    vector_first, keyword_first = chunk("vector"), chunk("keyword")
    vectors = [hit(vector_first), hit(keyword_first)]
    keywords = [hit(keyword_first), hit(vector_first)]
    vector_priority = fuse_rankings(vectors, keywords, HybridOptions(vector_weight=2), 1)
    keyword_priority = fuse_rankings(vectors, keywords, HybridOptions(keyword_weight=2), 1)
    assert vector_priority[0].chunk is vector_first
    assert keyword_priority[0].chunk is keyword_first


def test_duplicate_chunk_only_gets_one_vote_per_method():
    record = chunk("same")
    result = fuse_rankings([hit(record), hit(record)], [hit(record)], HybridOptions(), 10)
    assert len(result) == 1
    assert result[0].retrieval_score == pytest.approx(2 / 61)


def test_keyword_cache_rebuilds_after_same_id_text_update_and_keeps_metadata_fresh():
    from test_chroma_store import example

    record = example().embeddings[0].chunk
    engine = KeywordSearch()
    first = engine.search("Delivery", [record], 2)
    assert first[0].chunk is record
    changed = record.model_copy(update={"text": "Buyer Jane email", "end_char": 16})
    assert engine.search("Delivery", [changed], 2) == []
    assert engine.search("Buyer", [changed], 2)[0].chunk is changed
    assert len(engine.cache) == 2


def test_keyword_matching_ignores_question_words_and_preserves_identifiers():
    assert tokenize("What is the MODEL JA-207652?") == ["model", "ja-207652"]
    engine = KeywordSearch()
    assert engine.search("what is the", [chunk("Buyer")], 3) == []
    assert engine.search("unmatched", [chunk("Buyer")], 3) == []
    assert engine.search("Buyer", [], 3) == []


def test_settings_field_boost_and_explicit_override_precedence():
    settings = Settings(
        _env_file=None, search_keyword_weight=2, search_field_keyword_boosts={"contact_info": 1.5}
    )
    assert SearchTuning(field_name="contact_info").resolve(settings).keyword_weight == 3
    tuned = SearchTuning(
        field_name="contact_info", keyword_weight=4, vector_candidates=7, keyword_candidates=9
    ).resolve(settings)
    assert tuned.keyword_weight == 4
    assert tuned.vector_candidates == 7
    assert tuned.keyword_candidates == 9
    assert SearchTuning().resolve(settings).keyword_weight == 2


def test_environment_can_replace_field_defaults(monkeypatch):
    monkeypatch.setenv("RFP_SEARCH_FIELD_KEYWORD_BOOSTS", "{}")
    monkeypatch.setenv("RFP_SEARCH_VECTOR_CANDIDATES", "11")
    settings = Settings(_env_file=None)
    assert settings.search_field_keyword_boosts == {}
    assert SearchTuning(field_name="Product").resolve(settings).vector_candidates == 11
    assert SearchTuning(field_name="Product").resolve(settings).keyword_weight == 1


@pytest.mark.parametrize(
    "values",
    [
        {"keyword_weight": 0},
        {"vector_weight": float("nan")},
        {"keyword_candidates": 0},
        {"rrf_k": 0},
    ],
)
def test_invalid_overrides_are_rejected(values):
    with pytest.raises(ValidationError):
        SearchTuning(**values)
