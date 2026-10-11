"""Pack complete fields and their cited passages; never truncate validation evidence."""

import json

VALIDATION_MAX_EVIDENCE_CHARS = 12000
VALIDATION_MAX_CHARS = 16000
VALIDATION_MAX_CHUNKS = 15


def validation_payload(fields, evidence):
    ids = list(dict.fromkeys(cid for field in fields for cid in field.source_chunk_ids))
    lookup = {item["chunk_id"]: item for item in evidence}
    if any(cid not in lookup for cid in ids):
        raise ValueError("Validation is missing a cited passage")
    return {
        "fields": [field.model_dump() for field in fields],
        "evidence": [lookup[cid] for cid in ids],
    }


def fits(payload):
    return (
        len(payload["evidence"]) <= VALIDATION_MAX_CHUNKS
        and len(json.dumps(payload["evidence"], ensure_ascii=False))
        <= VALIDATION_MAX_EVIDENCE_CHARS
        and len(json.dumps(payload, ensure_ascii=False)) <= VALIDATION_MAX_CHARS
    )


def validation_batches(fields, evidence):
    batches = []
    pending = []
    for field in fields:
        candidate = validation_payload(pending + [field], evidence)
        if fits(candidate):
            pending.append(field)
            continue
        if pending:
            batches.append(validation_payload(pending, evidence))
        pending = [field]
        if not fits(validation_payload(pending, evidence)):
            raise ValueError(
                f"Validation input for {field.name} exceeds the budget; "
                "cannot validate without omitting cited evidence"
            )
    if pending:
        batches.append(validation_payload(pending, evidence))
    return batches
