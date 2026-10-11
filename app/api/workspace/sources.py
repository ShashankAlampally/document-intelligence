"""Translate core evidence dictionaries into browser-facing citations."""

from app.api.workspace_contracts import SourcePassage


def source_passage(source: dict) -> SourcePassage:
    return SourcePassage(
        table_id=source.get("table_id"),
        table_complete=source.get("table_complete"),
        source_chunk_ids=source.get("source_chunk_ids", []),
        file=source.get("file_name") or source["file"],
        page=source.get("page_number", source.get("page")),
        section=source.get("section"),
        text=source["text"],
        chunk_id=source.get("chunk_id"),
        discovery_id=source.get("discovery_id"),
        folder_name=source.get("folder_name"),
        similarity=source.get("similarity"),
        retrieval_score=source.get("retrieval_score"),
        rerank_score=source.get("rerank_score"),
        keyword_score=source.get("keyword_score"),
        vector_rank=source.get("vector_rank"),
        keyword_rank=source.get("keyword_rank"),
    )
