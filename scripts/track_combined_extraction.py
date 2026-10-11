"""Save group progress while using the same combined validator as the website."""

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from scripts.pipeline_report import save_record


def track_combined_extraction(model, tool, groups, directory, record):
    prior_trace = list(record["trace"])

    def save_group(group_name, result):
        record["fields"].update({name: field.model_dump() for name, field in result.fields.items()})
        record["trace"].extend({"field_group": group_name, **step} for step in result.trace)
        save_record(directory, record)
        print(f"{group_name}: draft saved; validation follows after all groups", flush=True)

    def save_step(trace):
        record["trace"] = prior_trace + trace
        save_record(directory, record)

    result = extract_bid_fields(
        model, {"search_documents": tool}, groups=groups, on_group=save_group, on_step=save_step
    )
    record["trace"] = prior_trace + result.trace
    if not result.error:
        record["fields"].update({name: field.model_dump() for name, field in result.fields.items()})
    record["validation_report"] = result.validation_report
    record["error"] = result.error
    record["status"] = "error" if result.error else "completed"
    save_record(directory, record)
