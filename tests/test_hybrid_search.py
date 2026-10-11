"""Real Chroma text retrieval with scripted query vectors; no model/API calls."""

import pytest

pytest.importorskip("chromadb")

from test_chroma_store import example
from test_search_service import Provider

from app.api.workspace_contracts import SelectedDocumentQuery
from app.config import Settings
from app.schemas.retrieval import HybridOptions
from app.schemas.search import SearchFilters
from app.search.chroma_store import ChromaVectorStore
from app.search.service import search_documents
from app.tools.document_search import SearchTool


def indexed_store(tmp_path):
    primary, other = example(), example("Other")
    for record, text in zip(
        primary.embeddings,
        ["General administrative policy", "Buyer Jane Email jane@example.org Phone 555-1234"],
    ):
        record.chunk.text = text
        record.chunk.end_char = len(text)
    store = ChromaVectorStore(tmp_path, "hybrid_test", primary.info)
    store.upsert(primary)
    store.upsert(other)
    return store, primary, other


def test_keyword_only_hit_can_win_and_filters_never_mix_uploads(tmp_path):
    store, primary, other = indexed_store(tmp_path)
    filters = SearchFilters(discovery_id=primary.embeddings[0].chunk.source.discovery_id)
    provider = Provider()
    dense = search_documents("Buyer email", provider, store, 1, filters)
    assert dense[0].chunk.text == "General administrative policy"
    options = HybridOptions(vector_candidates=1, keyword_candidates=5, keyword_weight=2)
    hybrid = search_documents("Buyer email", provider, store, 1, filters, options=options)
    assert hybrid[0].chunk == primary.embeddings[1].chunk
    assert hybrid[0].similarity is None
    assert hybrid[0].retrieval_score > 0
    assert hybrid[0].keyword_rank == 1
    assert hybrid[0].vector_rank is None
    assert len(provider.queries) == 2  # No document re-embedding.
    assert all(
        chunk.source.discovery_id != other.embeddings[0].chunk.source.discovery_id
        for chunk in store.list_chunks(filters)
    )


def test_tool_and_http_options_reach_shared_search_and_preserve_score_meaning(tmp_path):
    store, primary, _ = indexed_store(tmp_path)
    upload = primary.embeddings[0].chunk.source.discovery_id
    request = SelectedDocumentQuery(
        discovery_ids=[upload],
        question="Buyer email",
        top_k=1,
        vector_candidates=1,
        keyword_candidates=5,
        keyword_weight=2,
    )
    tool = SearchTool(
        Provider(),
        store,
        upload,
        settings=Settings(_env_file=None),
        options=request.model_dump(exclude={"question", "discovery_ids"}, exclude_none=True),
    )
    evidence = tool.run({"query": request.question, "field_name": "contact_info"})
    assert len(evidence) == 1
    assert evidence[0]["similarity"] is None
    assert evidence[0]["retrieval_score"] > 0
    assert evidence[0]["text"].startswith("Buyer Jane")
    assert evidence[0]["discovery_id"] == str(upload)


def test_both_methods_apply_file_and_document_role_filters(tmp_path):
    store, primary, _ = indexed_store(tmp_path)
    filters = SearchFilters(
        discovery_id=primary.embeddings[0].chunk.source.discovery_id,
        file_name="missing.pdf",
        doc_type="addendum",
    )
    assert store.list_chunks(filters) == []
    assert search_documents("Buyer", Provider(), store, 3, filters, options=HybridOptions()) == []
