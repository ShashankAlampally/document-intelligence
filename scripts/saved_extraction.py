"""Restore complete saved drafts and their exact cited evidence, without extraction."""

import json
from pathlib import Path
from uuid import UUID

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.models.check_fields import check_fields
from app.agents.extraction.models.field_catalog import FIELD_NAMES
from app.agents.extraction.models.fields import ExtractionDraft, FieldDraft
from app.agents.shared.select_evidence import EXTRACTION_MAX_CHARS, EXTRACTION_MAX_CHUNKS


def load_saved_extraction(path):
    path = Path(path).expanduser().resolve()
    if path.is_dir():
        path = path / "trace.json"
    record = json.loads(path.read_text())
    identity = UUID(record["discovery_id"])
    if set(record.get("fields", {})) != set(FIELD_NAMES):
        raise ValueError(
            "Saved run must contain all 20 extracted fields; incomplete runs cannot be validated"
        )
    evidence = {}
    for step in record.get("trace", []):
        if step["step"] == "retrieve_evidence":
            for chunk in step.get("output", []):
                evidence[chunk["chunk_id"]] = chunk
    fields = []
    for name in FIELD_NAMES:
        saved = record["fields"][name]
        ids = []
        for source in saved["sources"]:
            cid = source["chunk_id"]
            if source.get("discovery_id") and UUID(source["discovery_id"]) != identity:
                raise ValueError("Saved citation belongs to a different upload")
            if cid not in evidence:
                raise ValueError(f"Saved trace is missing the cited passage {cid}")
            chunk = evidence[cid]
            if (
                chunk["text"] != source["text"]
                or chunk["file_name"] != source["file"]
                or chunk.get("page_number") != source.get("page")
            ):
                raise ValueError(f"Saved field and trace disagree on cited passage {cid}")
            if chunk.get("discovery_id") and UUID(chunk["discovery_id"]) != identity:
                raise ValueError("Saved evidence belongs to a different upload")
            ids.append(cid)
        fields.append(
            FieldDraft(
                name=name,
                value=saved["value"],
                source_chunk_ids=ids,
                confidence=saved["confidence"],
                notes=saved.get("notes"),
            )
        )
    draft = ExtractionDraft(fields=fields)
    check_fields(draft, list(evidence.values()), FIELD_NAMES)
    state = ExtractionState(
        requested_fields=FIELD_NAMES,
        draft=draft,
        evidence=list(evidence.values()),
        trace=record.get("trace", []),
        search_top_k=5,
        max_evidence_chunks=EXTRACTION_MAX_CHUNKS,
        max_evidence_chars=EXTRACTION_MAX_CHARS,
    )
    return path, record, state
