"""Validate the combined draft in as few bounded calls as possible."""

from app.agents.extraction.models.validation import ValidationReport
from app.agents.extraction.models.validation_batches import validation_batches
from app.agents.extraction.nodes.review_validation_batch import review_validation_batch


def validate_fields(state, model, on_step=None):
    if state.error:
        return {}
    names = state.retry_fields or state.requested_fields
    fields = [field for field in state.draft.fields if field.name in names]
    trace = list(state.trace)
    try:
        batches = validation_batches(fields, state.evidence)
    except ValueError as error:
        return {
            "error": "Field validation failed (ValueError)",
            "trace": trace
            + [{"step": "validate_fields", "error": "ValueError", "error_detail": str(error)}],
        }
    decisions = []
    for index, payload in enumerate(batches, 1):
        report, step = review_validation_batch(
            payload, model, state.correction_attempts, index, len(batches)
        )
        trace.append(step)
        if on_step is not None:
            on_step(trace)
        if report is None:
            return {"error": f"Field validation failed ({step['error']})", "trace": trace}
        decisions.extend(report.fields)
    report = ValidationReport(fields=decisions)
    draft = state.draft.model_copy(deep=True)
    if state.correction_attempts:
        rejected = {item.name: item for item in decisions if item.decision != "accepted"}
        for field in draft.fields:
            if field.name in rejected:
                field.value = None
                field.confidence = 0
                field.notes = "Unresolved after validation retry: " + rejected[field.name].reason
        replacements = {item.name: item for item in decisions}
        report = ValidationReport(
            fields=[replacements.get(item.name, item) for item in state.validation.fields]
        )
    return {"draft": draft, "validation": report, "trace": trace}
