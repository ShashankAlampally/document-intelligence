"""Weighted reciprocal rank fusion; source scores retain their own meanings."""

from app.schemas.retrieval import HybridOptions


def fuse_rankings(vector_hits, keyword_hits, options: HybridOptions, top_k: int):
    combined = {}
    for method, hits, weight in [
        ("vector", vector_hits, options.vector_weight),
        ("keyword", keyword_hits, options.keyword_weight),
    ]:
        seen = set()
        for rank, hit in enumerate(hits, start=1):
            key = hit.chunk.chunk_id
            if key in seen:
                continue
            seen.add(key)
            if key not in combined:
                combined[key] = hit.model_copy(update={"retrieval_score": 0.0})
            result = combined[key]
            result.retrieval_score += weight / (options.rrf_k + rank)
            if method == "vector":
                result.vector_rank = rank
                result.similarity = hit.similarity
            else:
                result.keyword_rank = rank
                result.keyword_score = hit.keyword_score
    ranked = sorted(
        combined.values(), key=lambda hit: (-hit.retrieval_score, str(hit.chunk.chunk_id))
    )
    return ranked[:top_k]
