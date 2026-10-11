"""Ensure search embeds only the question and checks model compatibility."""

import pytest

from app.schemas.embeddings import EmbeddingInfo
from app.schemas.search import SearchFilters
from app.search.service import search_documents


class Provider:
    info = EmbeddingInfo(
        provider="test",
        model="test",
        revision="fixed",
        dimensions=2,
        max_tokens=100,
        library_version="test",
    )

    def __init__(self):
        self.queries = []

    def embed_query(self, query):
        self.queries.append(query)
        return [1.0, 0.0]

    def embed_documents(self, texts):
        raise AssertionError("Search must not embed documents")


class Store:
    def __init__(self):
        self.info = Provider.info.model_copy(deep=True)
        self.calls = []

    def search(self, vector, top_k, filters):
        self.calls.append((vector, top_k, filters))
        return []


def test_search_passes_query_vector_and_filters_only() -> None:
    provider, store = Provider(), Store()
    filters = SearchFilters(folder_name="Bid2")
    assert search_documents("When is delivery?", provider, store, 3, filters) == []
    assert provider.queries == ["When is delivery?"]
    assert store.calls == [([1.0, 0.0], 3, filters)]


def test_model_mismatch_does_not_embed_query() -> None:
    provider, store = Provider(), Store()
    store.info.query_prefix = "Changed instruction"
    with pytest.raises(ValueError, match="differs"):
        search_documents("Delivery?", provider, store)
    assert provider.queries == []


@pytest.mark.parametrize("query,top_k", [(" ", 5), ("Delivery?", 0)])
def test_invalid_inputs_fail_early(query, top_k) -> None:
    provider = Provider()
    with pytest.raises(ValueError):
        search_documents(query, provider, Store(), top_k)
    assert provider.queries == []
