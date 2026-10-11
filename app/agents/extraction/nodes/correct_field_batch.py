"""Retry rejected fields only; accepted fields and their sources are preserved."""

from app.agents.extraction.models.fields import ExtractionDraft
from app.agents.extraction.nodes.extract_fields import extract_fields
from app.agents.extraction.prompts.retrieval_plan import retrieval_plan
from app.agents.shared.retrieve_evidence import retrieve_evidence
from app.agents.shared.select_evidence import select_evidence


def correct_field_batch(state, model, available_tools):
    rejected = [item for item in state.validation.fields if item.decision != "accepted"]
    names = [item.name for item in rejected]
    working = state.model_copy(deep=True)
    working.requested_fields = names
    working.retry_fields = names
    working.correction_attempts = 1
    working.messages = [
        {
            "role": "user",
            "content": "Correct these rejected fields using the validation feedback: "
            + str([item.model_dump() for item in rejected]),
        }
    ]
    needs_search = [item.name for item in rejected if item.decision == "needs_evidence"]
    if needs_search:
        working.search_requests = retrieval_plan(needs_search)
        update = retrieve_evidence(working, available_tools)
        working.trace = update["trace"]
        if update.get("error"):
            return update
        # Final citations for accepted fields must still resolve. Correction sees
        # only the newly budgeted evidence plus evidence cited by rejected fields.
        cited = {
            cid
            for field in state.draft.fields
            if field.name in names
            for cid in field.source_chunk_ids
        }
        previous = [item for item in state.evidence if item["chunk_id"] in cited]
        new_ids = {item["chunk_id"] for item in update["evidence"]}
        working.evidence = select_evidence(
            [update["evidence"], [item for item in previous if item["chunk_id"] not in new_ids]],
            max_chunks=state.max_evidence_chunks,
            max_chars=state.max_evidence_chars,
            deduplicate_content=True,
        )
    else:
        cited = {
            cid
            for field in state.draft.fields
            if field.name in names
            for cid in field.source_chunk_ids
        }
        working.evidence = select_evidence(
            [[item for item in state.evidence if item["chunk_id"] in cited]],
            max_chunks=state.max_evidence_chunks,
            max_chars=state.max_evidence_chars,
        )
    update = extract_fields(working, model)
    if update.get("error"):
        return update
    replacements = {field.name: field for field in update["draft"].fields}
    draft = ExtractionDraft(
        fields=[replacements.get(field.name, field) for field in state.draft.fields]
    )
    known = {item["chunk_id"] for item in state.evidence}
    evidence = state.evidence + [item for item in working.evidence if item["chunk_id"] not in known]
    return {
        "draft": draft,
        "evidence": evidence,
        "retry_fields": names,
        "correction_attempts": 1,
        "trace": update["trace"],
    }
