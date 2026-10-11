"""Local persistent Chroma adapter using our existing embeddings exclusively."""

from pathlib import Path

from app.schemas.chunks import Chunk
from app.schemas.embeddings import EmbeddingInfo, EmbeddingResult, QueryEmbedding
from app.schemas.search import SearchFilters, SearchHit
from app.search.store_metadata import check_model, chunk_metadata, filter_metadata


class ChromaVectorStore:
    def __init__(
        self,
        path: str | Path,
        collection: str,
        info: EmbeddingInfo | None = None,
    ) -> None:
        try:
            import chromadb
            from chromadb.config import Settings
            from chromadb.errors import NotFoundError
        except ImportError as error:
            raise RuntimeError(
                "Install storage dependencies: pip install -e '.[storage]'"
            ) from error
        path = Path(path).expanduser().resolve()
        if info is None and not path.exists():
            raise ValueError("No saved index found; index a folder first")
        self.client = chromadb.PersistentClient(
            path=str(path), settings=Settings(anonymized_telemetry=False)
        )
        try:
            self.collection = self.client.get_collection(collection, embedding_function=None)
        except NotFoundError as error:
            if info is None:
                raise ValueError("No saved collection found; index a folder first") from error
            self.collection = self.client.create_collection(
                collection,
                embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
                metadata={"embedding_info": info.model_dump_json()},
            )
        metadata = self.collection.metadata or {}
        if "embedding_info" not in metadata:
            raise ValueError("Collection lacks embedding metadata; use a new collection")
        self.info = EmbeddingInfo.model_validate_json(metadata["embedding_info"])
        if info is not None:
            check_model(self.info, info)

    def count(self) -> int:
        return self.collection.count()

    def list_chunks(self, filters: SearchFilters | None = None) -> list[Chunk]:
        """Load saved text under the same filters as vector search; no embeddings."""
        chunks = []
        offset = 0
        while True:
            page = self.collection.get(
                where=filter_metadata(filters), limit=1000, offset=offset, include=["metadatas"]
            )
            chunks.extend(
                Chunk.model_validate_json(item["chunk_json"]) for item in page["metadatas"]
            )
            if len(page["ids"]) < 1000:
                return chunks
            offset += 1000

    def upsert(self, result: EmbeddingResult) -> int:
        # Revalidate mutable models before persisting any batch.
        result = EmbeddingResult.model_validate_json(result.model_dump_json())
        check_model(self.info, result.info)
        records = result.embeddings
        batch_size = self.client.get_max_batch_size()
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            self.collection.upsert(
                ids=[str(record.chunk.chunk_id) for record in batch],
                embeddings=[record.vector for record in batch],
                documents=[record.chunk.text for record in batch],
                metadatas=[chunk_metadata(record.chunk) for record in batch],
            )
        return len(records)

    def search(
        self, vector: list[float], top_k: int = 5, filters: SearchFilters | None = None
    ) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        validated = EmbeddingResult(
            info=self.info, query=QueryEmbedding(text="validation", vector=vector)
        )
        count = self.count()
        if count == 0:
            return []
        result = self.collection.query(
            query_embeddings=[validated.query.vector],
            n_results=min(top_k, count),
            where=filter_metadata(filters),
            include=["metadatas", "distances"],
        )
        return [
            SearchHit(
                chunk=Chunk.model_validate_json(metadata["chunk_json"]),
                similarity=1.0 - distance,
            )
            for metadata, distance in zip(result["metadatas"][0], result["distances"][0])
        ]
