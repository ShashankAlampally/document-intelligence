"""Correct rejected fields in the original small groups, never all 20 in one call."""

from app.agents.extraction.models.field_catalog import FIELD_GROUPS
from app.agents.extraction.models.validation import ValidationReport
from app.agents.extraction.nodes.correct_field_batch import correct_field_batch


def correct_fields(state, model, available_tools, on_step=None):
    rejected = [item for item in state.validation.fields if item.decision != "accepted"]
    working = state.model_copy(deep=True)
    for group_name, names in FIELD_GROUPS.items():
        decisions = [item for item in rejected if item.name in names]
        if not decisions:
            continue
        batch = working.model_copy(deep=True)
        batch.validation = ValidationReport(fields=decisions)
        update = correct_field_batch(batch, model, available_tools)
        start = len(working.trace)
        update["trace"][start:] = [
            {"field_group": group_name, **step} for step in update["trace"][start:]
        ]
        working.trace = update["trace"]
        if on_step is not None:
            on_step(working.trace)
        if update.get("error"):
            return {"error": update["error"], "trace": working.trace}
        working.draft = update["draft"]
        working.evidence = update["evidence"]
    return {
        "draft": working.draft,
        "evidence": working.evidence,
        "retry_fields": [item.name for item in rejected],
        "correction_attempts": 1,
        "trace": working.trace,
    }
