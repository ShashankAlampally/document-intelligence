"""Basic structure and citation checks, before the Extraction Validator Agent."""

from app.agents.extraction.models.fields import ExtractionDraft


def check_fields(draft: ExtractionDraft, evidence: list[dict], requested_fields: list[str]) -> None:
    names = [field.name for field in draft.fields]
    if len(names) != len(requested_fields) or set(names) != set(requested_fields):
        raise ValueError("Expected exactly one entry for each requested field")
    known_ids = {item["chunk_id"] for item in evidence}
    for field in draft.fields:
        if not set(field.source_chunk_ids).issubset(known_ids):
            raise ValueError("Field cites evidence that was not retrieved")
        if field.value is None:
            field.confidence = 0
            if field.source_chunk_ids:
                # Cited null values represent unresolved conflicts, not missing evidence.
                if not field.notes or not field.notes.strip():
                    raise ValueError("Unresolved fields require explanatory notes")
            else:
                field.notes = "Not found in retrieved evidence"
        else:
            if not field.value.strip() or not field.source_chunk_ids:
                raise ValueError("Non-empty values require citations")
