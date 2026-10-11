"""Track validation and correction of saved drafts into a new output directory."""

from time import perf_counter

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.graph.validation_workflow import build_validation_graph
from app.agents.extraction.models.build_result import build_result
from app.agents.extraction.models.validation_batches import (
    VALIDATION_MAX_CHARS,
    VALIDATION_MAX_CHUNKS,
    VALIDATION_MAX_EVIDENCE_CHARS,
)
from scripts.pipeline_report import save_record
from scripts.pipeline_tracking import TrackingModel, TrackingSearch


def run_saved_validation(state, previous, source_path, directory, model, search):
    started = perf_counter()
    record = dict(
        discovery_id=previous["discovery_id"],
        model=previous.get("model"),
        mode="validate_saved_drafts",
        status="running",
        pipeline_version="combined_validation_v2",
        resumed_from=str(source_path),
        prior_elapsed_seconds=previous.get("elapsed_seconds"),
        fields=previous["fields"].copy(),
        trace=list(state.trace),
        error=None,
        baseline=previous,
        configuration=previous.get("configuration", {}).copy(),
    )
    record["configuration"].update(
        validation_payload_chars=VALIDATION_MAX_CHARS,
        validation_evidence_chars=VALIDATION_MAX_EVIDENCE_CHARS,
        validation_evidence_chunks=VALIDATION_MAX_CHUNKS,
    )
    actual_settings = getattr(model, "settings", None)
    if actual_settings is not None:
        record["model"] = actual_settings.llm_model
        record["configuration"]["llm_max_tokens"] = actual_settings.llm_max_tokens
    save_record(directory, record)

    def save_step(trace):
        record["trace"] = trace
        save_record(directory, record)

    try:
        graph = build_validation_graph(
            TrackingModel(model, directory),
            {"search_documents": TrackingSearch(search, directory)},
            on_step=save_step,
        )
        final = ExtractionState.model_validate(graph.invoke(state, config={"recursion_limit": 6}))
        result = build_result(final)
        record.update(
            status=result.status,
            error=result.error,
            trace=result.trace,
            validation_report=result.validation_report,
        )
        if not result.error:
            record["fields"] = {name: field.model_dump() for name, field in result.fields.items()}
    except KeyboardInterrupt:
        record.update(
            status="interrupted", error="Validation interrupted; completed steps were saved"
        )
    except Exception as error:
        record.update(status="error", error=f"Validation failed ({type(error).__name__}): {error}")
    finally:
        record["elapsed_seconds"] = round(perf_counter() - started, 2)
        save_record(directory, record)
    return record
