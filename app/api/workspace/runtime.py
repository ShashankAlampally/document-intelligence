"""Reuse one embedding model and database per server process, loaded on demand."""

from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from app.api.workspace.files import save_json
from app.config import Settings
from app.schemas.chunks import ChunkSettings
from app.schemas.search import IndexReport
from app.search.chroma_store import ChromaVectorStore
from app.search.cross_encoder_reranker import CrossEncoderReranker
from app.search.indexer import index_folder
from app.search.keyword_search import KeywordSearch
from app.search.local_embeddings import LocalEmbeddingProvider
from app.shared.groq_client import GroqModel


class PipelineRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = LocalEmbeddingProvider(settings)
        self._store = None
        self._model = None
        self.keyword_search = KeywordSearch()
        self.reranker = CrossEncoderReranker(settings)

    @property
    def store(self):
        if self._store is None:
            self._store = ChromaVectorStore(
                self.settings.vector_db_dir, self.settings.vector_collection, self.provider.info
            )
        return self._store

    @property
    def model(self):
        if self._model is None:
            if not self.settings.groq_api_key.get_secret_value().strip():
                raise HTTPException(503, "Set RFP_GROQ_API_KEY in .env, then restart the server")
            self._model = GroqModel(self.settings)
        return self._model

    def index(self, folder: Path) -> IndexReport:
        report = index_folder(
            folder,
            self.provider,
            self.store,
            ChunkSettings(
                max_chars=1000,
                overlap_chars=100,
                structure_aware=self.settings.index_structure_aware,
            ),
        )
        path = self.settings.vector_db_dir.parent / "manifests" / f"{report.discovery_id}.json"
        save_json(path, report.model_dump_json(indent=2))
        return report

    def require_uploads(self, discovery_ids: list[UUID]) -> None:
        for discovery_id in discovery_ids:
            path = self.settings.vector_db_dir.parent / "manifests" / f"{discovery_id}.json"
            if not path.is_file():
                raise HTTPException(404, f"Indexed upload not found: {discovery_id}")
            report = IndexReport.model_validate_json(path.read_text(encoding="utf-8"))
            if report.discovery_id != discovery_id or report.stored_chunks < 1:
                raise HTTPException(409, "Selected folder is not ready for questions")
