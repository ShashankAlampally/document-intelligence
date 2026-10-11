"""Offline scoring, token safety and connected retrieval regression checks."""

import pytest
from pydantic import ValidationError
from test_chroma_store import example
from test_hybrid_search import indexed_store
from test_search_service import Provider
from test_table_retrieval import parts, table_document

from app.api.workspace.sources import source_passage
from app.api.workspace_contracts import SelectedDocumentQuery
from app.config import Settings
from app.schemas.embeddings import EmbeddedChunk, EmbeddingResult
from app.schemas.retrieval import HybridOptions, SearchTuning
from app.schemas.search import SearchFilters, SearchHit
from app.search.chroma_store import ChromaVectorStore
from app.search.cross_encoder_reranker import CrossEncoderReranker
from app.search.rerank_windows import passage_windows
from app.search.service import search_documents
from app.tools.document_search import SearchTool


class Model:
    max_length = 100

    def __init__(self):
        self.pairs = []

    def tokenizer(self, query, text, **kwargs):
        return {"input_ids": list(range(len(query) + len(text) + 3))}

    def predict(self, pairs, **kwargs):
        self.pairs.extend(pairs)
        return [8.0 if "Buyer Jane" in text else -2.0 for query, text in pairs]


def reranker(model=None):
    result = CrossEncoderReranker(Settings(_env_file=None))
    result._model = model or Model()
    return result


def test_scores_reorder_without_changing_original_text_or_citations():
    batch = example()
    first, second = [
        SearchHit(chunk=record.chunk, similarity=0.7, retrieval_score=0.01)
        for record in batch.embeddings
    ]
    second.chunk.text = "Buyer Jane email jane@example.org"
    second.chunk.end_char = len(second.chunk.text)
    before = [hit.model_dump_json() for hit in [first, second]]
    result = reranker().rerank("Who is the buyer?", [first, second], 2)
    assert result[0].chunk == second.chunk
    assert result[0].rerank_score == 8
    assert result[0].similarity == 0.7
    assert result[0].retrieval_score == 0.01
    assert [hit.model_dump_json() for hit in [first, second]] == before
    assert len(reranker().rerank("Buyer", [first, second], 1)) == 1


def test_long_passages_are_fully_windowed_and_best_window_score_is_retained():
    hit = SearchHit(chunk=example().embeddings[0].chunk)
    hit.chunk.text = "Details " * 100 + "Buyer Jane" + " end" * 20
    hit.chunk.end_char = len(hit.chunk.text)
    model = Model()
    result = reranker(model).rerank("Buyer?", [hit], 1)[0]
    assert all(len(q) + len(text) + 3 <= model.max_length for q, text in model.pairs)
    assert any("Buyer Jane" in text for q, text in model.pairs)
    assert result.rerank_score == 8
    assert result.chunk.text == hit.chunk.text
    # Every character of an indivisible string still reaches at least one window.
    text = "abcdefghij" * 100
    windows = passage_windows("q", text, lambda q, t: len(q) + len(t), 40)
    cursor = 0
    for window in windows:
        start = text.find(window, max(0, cursor - 10))
        assert start <= cursor
        cursor = max(cursor, start + len(window))
    assert cursor == len(text)


def test_ties_keep_rrf_order_and_empty_input_does_not_load_model():
    hits = [SearchHit(chunk=r.chunk) for r in example().embeddings]
    assert [h.chunk.chunk_id for h in reranker().rerank("Delivery", hits, 2)] == [
        h.chunk.chunk_id for h in hits
    ]
    assert CrossEncoderReranker(Settings(_env_file=None)).rerank("q", [], 1) == []


@pytest.mark.parametrize("scores", [[float("nan")], [], [float("inf")]])
def test_invalid_model_scores_raise_clear_errors(scores):
    class Broken(Model):
        def predict(self, pairs, **kwargs):
            return scores

    with pytest.raises(ValueError, match="score"):
        reranker(Broken()).rerank("q", [SearchHit(chunk=example().embeddings[0].chunk)], 1)


def test_oversized_query_is_not_silently_truncated():
    model = Model()
    with pytest.raises(ValueError, match="Question exceeds"):
        reranker(model).rerank("q" * 200, [SearchHit(chunk=example().embeddings[0].chunk)], 1)
    assert model.pairs == []


@pytest.mark.parametrize("mode", ["vector", "hybrid"])
def test_candidate_reranking_reaches_tool_api_and_keeps_upload_filter(tmp_path, mode):
    store, primary, other = indexed_store(tmp_path)
    upload = primary.embeddings[0].chunk.source.discovery_id
    scoring = reranker()
    request = SelectedDocumentQuery(
        discovery_ids=[upload],
        question="Buyer?",
        top_k=1,
        mode=mode,
        rerank=True,
        rerank_candidates=2,
        vector_candidates=1,
        keyword_candidates=1,
    )
    tool = SearchTool(
        Provider(),
        store,
        upload,
        settings=Settings(_env_file=None),
        options=request.model_dump(exclude={"question", "discovery_ids"}, exclude_none=True),
        reranker=scoring,
    )
    evidence = tool.run({"query": request.question})
    assert len(evidence) == 1
    assert evidence[0]["text"].startswith("Buyer Jane")
    assert evidence[0]["discovery_id"] == str(upload)
    assert source_passage(evidence[0]).rerank_score == 8
    assert len(scoring._model.pairs) == 2  # Rerank BEFORE selecting final top_k=1.
    assert all("Warranty" not in text for q, text in scoring._model.pairs)


def test_disabled_and_empty_searches_never_call_reranker(tmp_path):
    store, primary, _ = indexed_store(tmp_path)

    class MustNotCall:
        def rerank(self, *args):
            raise AssertionError("Disabled/empty reranking must not run")

    disabled = search_documents(
        "Buyer", Provider(), store, 1, options=HybridOptions(rerank=False), reranker=MustNotCall()
    )
    assert disabled[0].rerank_score is None
    assert (
        search_documents(
            "Buyer",
            Provider(),
            store,
            1,
            SearchFilters(file_name="missing.pdf"),
            options=HybridOptions(rerank=True),
            reranker=MustNotCall(),
        )
        == []
    )


def test_reranking_returns_original_table_chunk_without_expansion(tmp_path):
    document = table_document()
    chunks = parts(document)
    info = example().info
    store = ChromaVectorStore(tmp_path, "rerank_table", info)
    store.upsert(
        EmbeddingResult(
            info=info, embeddings=[EmbeddedChunk(chunk=c, vector=[1.0, 0.0]) for c in chunks]
        )
    )

    class Scoring:
        def rerank(self, query, hits, top_k):
            assert all(hit.chunk.table_complete is False for hit in hits)
            return [hits[-1].model_copy(update={"rerank_score": 9.0})]

    hits = search_documents(
        "products", Provider(), store, 1, options=HybridOptions(rerank=True), reranker=Scoring()
    )
    assert hits[0].chunk.table_complete is False
    assert hits[0].chunk in chunks
    assert len(hits[0].chunk.table_rows) < len(document.tables[0].rows)
    assert hits[0].chunk.source_chunk_ids == []
    assert hits[0].rerank_score == 9


def test_configuration_and_request_overrides():
    settings = Settings(_env_file=None, search_rerank=True, search_rerank_candidates=10)
    assert SearchTuning().resolve(settings).rerank is True
    assert SearchTuning(rerank=False, rerank_candidates=5).resolve(settings).rerank is False
    assert SearchTuning(rerank_candidates=5).resolve(settings).rerank_candidates == 5
    with pytest.raises(ValidationError):
        SearchTuning(rerank_candidates=0)


def test_model_load_is_lazy_reused_and_pinned(monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = []
    model = Model()

    def load(name, **kwargs):
        calls.append((name, kwargs))
        return model

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=load))
    scoring = CrossEncoderReranker(Settings(_env_file=None))
    assert calls == []
    assert scoring._load_model() is model
    assert scoring._load_model() is model
    assert len(calls) == 1
    assert calls[0][1]["revision"] == scoring.settings.reranker_revision
    assert calls[0][1]["trust_remote_code"] is False
    assert calls[0][1]["max_length"] == 512


def test_server_reuses_reranker_for_search_requests_without_groq(tmp_path):
    from app.api.workspace.queries import search_reply
    from app.api.workspace.runtime import PipelineRuntime

    store, primary, _ = indexed_store(tmp_path)
    upload = primary.embeddings[0].chunk.source.discovery_id
    runtime = PipelineRuntime(Settings(_env_file=None, search_rerank=True))
    runtime.provider = Provider()
    runtime._store = store
    runtime.reranker = reranker()
    query = SelectedDocumentQuery(question="Buyer?", discovery_ids=[upload], top_k=1)
    for _ in range(2):
        reply = search_reply(runtime, query)
        assert reply.sources[0].rerank_score == 8
        assert reply.sources[0].text.startswith("Buyer Jane")
    assert len(runtime.reranker._model.pairs) == 4
    assert runtime._model is None


def test_reranker_failure_uses_existing_agent_error_path(tmp_path):
    from app.agents.shared.retrieve_evidence import retrieve_evidence
    from app.agents.shared.state import ToolState

    class Broken:
        def rerank(self, *args):
            raise RuntimeError("Model unavailable")

    store, primary, _ = indexed_store(tmp_path)
    tool = SearchTool(
        Provider(),
        store,
        primary.embeddings[0].chunk.source.discovery_id,
        settings=Settings(_env_file=None, search_rerank=True),
        reranker=Broken(),
    )
    result = retrieve_evidence(ToolState(search_queries=["Buyer"]), {"search_documents": tool})
    assert result["error"] == "Search failed (RuntimeError)"
    assert result["trace"][0]["error"] == "RuntimeError"
