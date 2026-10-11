"""Agent-facing search tool scoped to the selected uploads."""

from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.config import Settings
from app.schemas.metadata import DocumentType
from app.schemas.retrieval import SearchTuning
from app.schemas.search import SearchFilters
from app.search.cross_encoder_reranker import CrossEncoderReranker
from app.search.embedding_provider import EmbeddingProvider
from app.search.keyword_search import KeywordSearch
from app.search.service import search_documents
from app.search.vector_store import VectorStore
from app.tools.selected_uploads import selected_uploads


class SearchInput(SearchTuning):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, description="Question or keywords to search")
    required_terms: list[str] = Field(default_factory=list, max_length=8)
    top_k: int = Field(default=3, ge=1, le=20)
    file_name: str | None = Field(default=None, min_length=1, max_length=500)
    doc_type: DocumentType | None = Field(default=None, description="Restrict document role")
    addendum_number: int | None = Field(default=None, ge=1, description="Restrict addendum number")

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query cannot be blank")
        return value.strip()


class SearchTool:
    returns_document_evidence = True

    def __init__(
        self,
        provider: EmbeddingProvider,
        store: VectorStore,
        discovery_id: UUID | list[UUID],
        *,
        options: dict | None = None,
        settings: Settings | None = None,
        keyword_search: KeywordSearch | None = None,
        reranker=None,
    ) -> None:
        self.options = options or {}
        SearchInput.model_validate({"query": "validate options", **self.options})
        self.provider = provider
        self.store = store
        self.settings = settings or getattr(provider, "settings", None) or Settings(_env_file=None)
        self.keyword_search = keyword_search if keyword_search is not None else KeywordSearch()
        self.reranker = reranker if reranker is not None else CrossEncoderReranker(self.settings)
        self.discovery_ids = selected_uploads(discovery_id)
        self.filters = SearchFilters(discovery_id=self.discovery_ids[0])
        self._heading_context = None
        self._stored_chunks = None

    def stored_chunks(self):
        if self._stored_chunks is None:
            self._stored_chunks = []
            for discovery_id in self.discovery_ids:
                self._stored_chunks.extend(
                    self.store.list_chunks(SearchFilters(discovery_id=discovery_id))
                )
        return self._stored_chunks

    def heading_context(self):
        from app.search.heading_context import build_heading_context

        if self._heading_context is None:
            self._heading_context = build_heading_context(self.stored_chunks())
        return self._heading_context

    def qa_supporting_passages(self, evidence):
        from app.search.qa_context import continuation_evidence, question_continuations

        return self.add_heading_context(
            [
                continuation_evidence(chunk, seed_id)
                for chunk, seed_id in question_continuations(evidence, self.stored_chunks())
            ]
        )

    def add_heading_context(self, evidence):
        self.heading_context()
        return [
            {**item, "heading_context": self._heading_context[item["chunk_id"]]}
            if item["chunk_id"] in self._heading_context
            else item
            for item in evidence
        ]

    @property
    def definition(self) -> dict:
        """Function description sent to the model; upload selection stays in code."""
        return {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Search each selected upload for evidence with source references.",
                "parameters": SearchInput.model_json_schema(),
            },
        }

    def run(self, arguments: dict) -> list[dict]:
        request = SearchInput.model_validate({**arguments, **self.options})
        hits = []
        for discovery_id in self.discovery_ids:
            filters = SearchFilters(
                discovery_id=discovery_id,
                file_name=request.file_name,
                doc_type=request.doc_type,
                addendum_number=request.addendum_number,
            )
            hits.extend(
                search_documents(
                    request.query,
                    self.provider,
                    self.store,
                    request.top_k,
                    filters,
                    options=request.resolve(self.settings),
                    keyword_search=self.keyword_search,
                    reranker=self.reranker,
                    required_terms=request.required_terms,
                    heading_context=self.heading_context() if request.required_terms else None,
                )
            )
        evidence = [
            {
                "chunk_id": str(hit.chunk.chunk_id),
                "discovery_id": str(hit.chunk.source.discovery_id),
                "folder_name": hit.chunk.source.folder_name,
                "file_name": hit.chunk.source.file_name,
                "page_number": hit.chunk.page_number,
                "section": hit.chunk.section,
                "doc_type": hit.chunk.source.doc_type,
                "addendum_number": hit.chunk.source.addendum_number,
                "document_date": (
                    hit.chunk.source.document_date.isoformat()
                    if hit.chunk.source.document_date
                    else None
                ),
                "text": hit.chunk.text,
                "content_type": getattr(hit.chunk, "content_type", "text"),
                "similarity": hit.similarity,
                "retrieval_score": getattr(hit, "retrieval_score", None),
                "rerank_score": getattr(hit, "rerank_score", None),
                "keyword_score": getattr(hit, "keyword_score", None),
                "vector_rank": getattr(hit, "vector_rank", None),
                "keyword_rank": getattr(hit, "keyword_rank", None),
            }
            for hit in hits
        ]
        for item, hit in zip(evidence, hits):
            if getattr(hit.chunk, "table_id", None) is not None:
                item.update(
                    table_id=str(hit.chunk.table_id),
                    table_complete=hit.chunk.table_complete,
                    table_row_start=hit.chunk.table_row_start,
                    table_row_end=hit.chunk.table_row_end,
                    table_total_rows=hit.chunk.table_total_rows,
                    source_chunk_ids=[str(value) for value in hit.chunk.source_chunk_ids],
                )
        return evidence
