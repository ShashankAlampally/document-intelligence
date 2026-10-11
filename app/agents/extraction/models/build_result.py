"""Resolve draft citations into the API's existing field/source format."""

from app.agents.extraction.models.fields import ExtractedField, ExtractionResult


def build_result(state):
    if state.error:
        return ExtractionResult(status="error", error=state.error, trace=state.trace)
    if state.draft is None:
        return ExtractionResult(
            status="error", error="Agent finished without a field draft", trace=state.trace
        )
    evidence = {item["chunk_id"]: item for item in state.evidence}
    fields = {}
    for field in state.draft.fields:
        sources = []
        for chunk_id in dict.fromkeys(field.source_chunk_ids):
            chunk = evidence[chunk_id]
            sources.append(
                {
                    "file": chunk["file_name"],
                    "discovery_id": chunk.get("discovery_id"),
                    "folder_name": chunk.get("folder_name"),
                    "page": chunk["page_number"],
                    "section": chunk["section"],
                    "chunk_id": chunk_id,
                    "text": chunk["text"],
                    "doc_type": chunk.get("doc_type", "unknown"),
                    "addendum_number": chunk.get("addendum_number"),
                    "document_date": chunk.get("document_date"),
                }
            )
            if chunk.get("table_id"):
                sources[-1].update(
                    {
                        key: chunk[key]
                        for key in (
                            "table_id",
                            "table_complete",
                            "source_chunk_ids",
                            "table_row_start",
                            "table_row_end",
                            "table_total_rows",
                        )
                    }
                )
        fields[field.name] = ExtractedField(
            value=field.value,
            sources=sources,
            confidence=field.confidence,
            notes=field.notes,
        )
    return ExtractionResult(
        status="completed",
        fields=fields,
        trace=state.trace,
        validation_report=[
            {
                "correction_attempts": state.correction_attempts,
                "fields": state.validation.model_dump()["fields"],
            }
        ]
        if state.validation
        else [],
    )
