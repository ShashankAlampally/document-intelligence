"""Find one bounded continuation for a retrieved addendum question."""


def question_continuations(evidence, stored_chunks):
    by_id = {str(chunk.chunk_id): chunk for chunk in stored_chunks}
    selected = {item["chunk_id"] for item in evidence}
    added = []
    for item in evidence:
        seed = by_id.get(item["chunk_id"])
        if seed is None or seed.source.doc_type != "addendum" or "?" not in seed.text:
            continue
        if seed.content_type != "text" or seed.page_number is None:
            continue
        candidates = []
        for chunk in stored_chunks:
            if chunk.source != seed.source or chunk.content_type != "text":
                continue
            if chunk.page_number == seed.page_number:
                if chunk.block_index != seed.block_index or chunk.end_char <= seed.end_char:
                    continue
                if not seed.start_char < chunk.start_char <= seed.end_char + 300:
                    continue
            elif chunk.page_number == seed.page_number + 1:
                pass
            else:
                continue
            candidates.append(chunk)
        candidates.sort(key=lambda chunk: (chunk.page_number, chunk.block_index, chunk.start_char))
        if candidates and str(candidates[0].chunk_id) not in selected:
            neighbor = candidates[0]
            selected.add(str(neighbor.chunk_id))
            added.append((neighbor, item["chunk_id"]))
    return added


def continuation_evidence(chunk, seed_id):
    return {
        "chunk_id": str(chunk.chunk_id),
        "discovery_id": str(chunk.source.discovery_id),
        "folder_name": chunk.source.folder_name,
        "file_name": chunk.source.file_name,
        "page_number": chunk.page_number,
        "section": chunk.section,
        "doc_type": chunk.source.doc_type,
        "addendum_number": chunk.source.addendum_number,
        "document_date": (
            chunk.source.document_date.isoformat() if chunk.source.document_date else None
        ),
        "text": chunk.text,
        "context_for_chunk_id": seed_id,
        "context_reason": "Nearby continuation; verify which question its answer belongs to",
    }
