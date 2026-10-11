"""Cache the configured public embedding model during the Docker image build."""

import os

from sentence_transformers import CrossEncoder, SentenceTransformer


def main() -> None:
    model = SentenceTransformer(
        os.environ["RFP_EMBEDDING_MODEL"],
        revision=os.environ["RFP_EMBEDDING_REVISION"],
        cache_folder=os.environ["RFP_EMBEDDING_CACHE_DIR"],
        device="cpu",
    )
    # Confirm that the cached model can actually produce an embedding.
    model.encode(["Embedding model build verification"], normalize_embeddings=True)
    reranker = CrossEncoder(
        os.environ["RFP_RERANKER_MODEL"],
        revision=os.environ["RFP_RERANKER_REVISION"],
        cache_folder=os.environ["RFP_RERANKER_CACHE_DIR"],
        device="cpu",
    )
    reranker.predict([("delivery deadline", "Delivery within 45 days of award")])


if __name__ == "__main__":
    main()
