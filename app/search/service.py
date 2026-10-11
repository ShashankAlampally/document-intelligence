"""Vector or hybrid retrieval over saved chunks; no document re-embedding."""

from app.schemas.embeddings import EmbeddingResult, QueryEmbedding
from app.schemas.retrieval import HybridOptions
from app.schemas.search import SearchFilters, SearchHit
from app.search.embedding_provider import EmbeddingProvider
from app.search.fusion import fuse_rankings
from app.search.keyword_search import KeywordSearch
from app.search.store_metadata import check_model
from app.search.vector_store import VectorStore


def search_documents(
    query: str,
    provider: EmbeddingProvider,
    store: VectorStore,
    top_k: int = 5,
    filters: SearchFilters | None = None,
    *,
    options: HybridOptions | None = None,
    keyword_search: KeywordSearch | None = None,
    reranker=None,
    required_terms: list[str] | None = None,
    heading_context: dict | None = None,
) -> list[SearchHit]:
    if not query.strip():
        raise ValueError("Query cannot be empty or whitespace-only")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    check_model(store.info, provider.info)
    result = EmbeddingResult(
        info=store.info, query=QueryEmbedding(text=query, vector=provider.embed_query(query))
    )
    rerank_enabled = options is not None and options.rerank
    candidate_count = top_k
    if rerank_enabled:
        candidate_count = max(top_k, options.rerank_candidates)
    if options is None or options.mode == "vector":
        hits = store.search(result.query.vector, candidate_count, filters)
    else:
        vector_count = options.vector_candidates
        keyword_count = options.keyword_candidates
        if rerank_enabled:
            vector_count = max(vector_count, candidate_count)
            keyword_count = max(keyword_count, candidate_count)
        vector_hits = store.search(result.query.vector, vector_count, filters)
        keywords = keyword_search if keyword_search is not None else KeywordSearch()
        keyword_hits = keywords.search(query, store.list_chunks(filters), keyword_count)
        if required_terms:
            vector_hits = matching_terms(vector_hits, required_terms, heading_context)
            keyword_hits = matching_terms(keyword_hits, required_terms, heading_context)
        hits = fuse_rankings(vector_hits, keyword_hits, options, candidate_count)
    if required_terms:
        hits = matching_terms(hits, required_terms, heading_context)
    if rerank_enabled and hits:
        if reranker is None:
            raise ValueError("Enabled reranking requires a reranker instance")
        if heading_context:
            hits = [with_heading(hit, heading_context) for hit in hits]
        hits = reranker.rerank(query, hits, top_k)
    return hits


def with_heading(hit, contexts):
    context = contexts.get(str(hit.chunk.chunk_id))
    if context is None:
        return hit
    chunk = hit.chunk.model_copy(update={"heading": context["heading"]})
    return hit.model_copy(update={"chunk": chunk})


def matching_terms(hits, terms, contexts=None):
    """Topic anchors match passage text or an explicitly recovered nearby heading."""
    matching = []
    for hit in hits:
        context = (contexts or {}).get(str(hit.chunk.chunk_id), {})
        text = (context.get("heading", "") + " " + hit.chunk.text).casefold()
        if all(term.casefold() in text for term in terms if term.strip()):
            matching.append(hit)
    return matching
