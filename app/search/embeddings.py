"""Associate provider vectors with chunk evidence; no persistence or model imports."""

from app.schemas.chunks import Chunk
from app.schemas.embeddings import EmbeddedChunk, EmbeddingResult, QueryEmbedding
from app.search.embedding_provider import EmbeddingProvider
from app.search.token_safe_chunks import fit_chunks_to_tokens


def embed_chunks(
    chunks: list[Chunk], provider: EmbeddingProvider, query: str | None = None
) -> EmbeddingResult:
    """Embed in input order and validate the provider's output contract."""
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ValueError("Embedding input contains duplicate chunk IDs")
    if query is not None and not query.strip():
        raise ValueError("Query cannot be empty or whitespace-only")
    info = provider.info.model_copy(deep=True)
    count_tokens = getattr(provider, "count_tokens", None)
    if count_tokens is not None:
        chunks = fit_chunks_to_tokens(chunks, count_tokens, info.max_tokens)
    vectors = provider.embed_documents([chunk.text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("Provider returned a different number of vectors than input chunks")
    records = [
        EmbeddedChunk(chunk=chunk.model_copy(deep=True), vector=vector)
        for chunk, vector in zip(chunks, vectors)
    ]
    query_result = (
        QueryEmbedding(text=query.strip(), vector=provider.embed_query(query))
        if query is not None
        else None
    )
    return EmbeddingResult(info=info, embeddings=records, query=query_result)
