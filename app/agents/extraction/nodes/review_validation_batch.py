"""Make one validator call for a bounded payload and record its behavior."""

import json
from time import perf_counter

from app.agents.extraction.models.validation import ValidationReport
from app.agents.extraction.prompts.validation import validation_instructions


def review_validation_batch(payload, model, attempt, batch_index, batch_count):
    started = perf_counter()
    names = [field["name"] for field in payload["fields"]]
    messages = [
        {"role": "system", "content": validation_instructions(names)},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    trace = {
        "step": "validate_fields",
        "input": messages,
        "correction_attempts": attempt,
        "batch_index": batch_index,
        "batch_count": batch_count,
        "payload_chars": len(messages[1]["content"]),
        "evidence_chars": len(json.dumps(payload["evidence"], ensure_ascii=False)),
        "usage": {},
        "model_called": False,
    }
    try:
        if not payload["evidence"]:
            report = ValidationReport(
                fields=[
                    {
                        "name": name,
                        "decision": "needs_evidence",
                        "reason": "No evidence retrieved for this field",
                    }
                    for name in names
                ]
            )
        else:
            schema = ValidationReport.model_json_schema()
            schema["$defs"]["FieldValidation"]["properties"]["name"]["enum"] = names
            trace["model_called"] = True
            response = model.complete(
                messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "field_validation",
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
            trace["usage"] = response.get("usage", {})
            if response.get("finish_reason") == "length":
                raise ValueError("Validation output was truncated")
            report = ValidationReport.model_validate_json(response["message"].get("content") or "")
        found = [item.name for item in report.fields]
        if len(found) != len(names) or set(found) != set(names):
            raise ValueError("Expected one validation decision per requested field")
        if any(not item.reason.strip() for item in report.fields):
            raise ValueError("Validation decisions require a reason")
        for item in report.fields:
            field = next(field for field in payload["fields"] if field["name"] == item.name)
            if not field["source_chunk_ids"]:
                item.decision = "needs_evidence"
                item.reason = "No cited evidence supports this field; " + item.reason
        trace["output"] = report.model_dump()
        return report, trace
    except Exception as error:
        trace.update(error=type(error).__name__, error_detail=str(error))
        return None, trace
    finally:
        trace["latency_seconds"] = perf_counter() - started
