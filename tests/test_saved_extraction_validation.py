"""Resume validation from saved drafts without initial extraction or file mutation."""

import json
from uuid import uuid4

import pytest
from test_combined_extraction_validation import CombinedModel
from test_extraction_agent import FakeSearch
from test_extraction_groups import GroupModel

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from scripts import validate_saved_extraction
from scripts.saved_extraction import load_saved_extraction
from scripts.saved_validation_run import run_saved_validation


class SavedSearch(FakeSearch):
    discovery_ids = ["offline-upload"]

    def add_heading_context(self, evidence):
        return evidence


def saved_run(tmp_path):
    result = extract_bid_fields(GroupModel(), {"search_documents": FakeSearch()})
    record = {
        "discovery_id": str(uuid4()),
        "model": "scripted",
        "mode": "live_extraction",
        **result.model_dump(),
        "status": "error",
        "error": "Old budget failure",
    }
    directory = tmp_path / "original"
    directory.mkdir()
    source = directory / "trace.json"
    source.write_text(json.dumps(record))
    return source


def test_saved_run_validates_without_repeating_extraction_and_preserves_original(tmp_path):
    source = saved_run(tmp_path)
    original = source.read_text()
    path, record, state = load_saved_extraction(source.parent)
    model = GroupModel()
    search = SavedSearch()
    result = run_saved_validation(state, record, path, tmp_path / "new", model, search)
    assert result["status"] == "completed"
    assert len(model.calls) == 1
    assert model.calls[0][1]["response_format"]["json_schema"]["name"] == "field_validation"
    assert not search.calls
    assert len(result["fields"]) == 20
    assert result["groq_diagnostics"]["model_calls_started"] == 1
    assert len(result["validation_report"][0]["fields"]) == 20
    assert source.read_text() == original


def test_saved_validation_corrects_only_rejected_field(tmp_path):
    source = saved_run(tmp_path)
    path, record, state = load_saved_extraction(source)
    model = CombinedModel({"Delivery Date": "needs_evidence"})
    search = SavedSearch()
    result = run_saved_validation(state, record, path, tmp_path / "new", model, search)
    assert result["status"] == "completed"
    assert model.extractions == [["Delivery Date"]]
    assert len(model.calls) == 3  # validation, one correction, validation.
    assert [call["field_name"] for call in search.calls] == ["Delivery Date"]
    assert result["fields"]["Title"] == record["fields"]["Title"]


@pytest.mark.parametrize(
    "problem", ["incomplete", "missing_passage", "mismatched_text", "other_upload"]
)
def test_invalid_saved_drafts_are_rejected_before_model_calls(tmp_path, problem):
    source = saved_run(tmp_path)
    record = json.loads(source.read_text())
    if problem == "incomplete":
        del record["fields"]["Title"]
    elif problem == "missing_passage":
        record["trace"] = []
    elif problem == "mismatched_text":
        record["fields"]["Title"]["sources"][0]["text"] = "different text"
    else:
        record["fields"]["Title"]["sources"][0]["discovery_id"] = str(uuid4())
    source.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        load_saved_extraction(source)


def test_prepare_only_never_creates_model_or_database(tmp_path, monkeypatch):
    source = saved_run(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Preflight must not instantiate services")

    monkeypatch.setattr(validate_saved_extraction, "GroqModel", forbidden)
    monkeypatch.setattr(validate_saved_extraction, "ChromaVectorStore", forbidden)
    monkeypatch.setattr("sys.argv", ["validate", str(source.parent), "--prepare-only"])
    validate_saved_extraction.main()


def test_validation_interruption_is_saved_without_overwriting_original(tmp_path):
    class InterruptedModel(GroupModel):
        def complete(self, *args, **kwargs):
            raise KeyboardInterrupt()

    source = saved_run(tmp_path)
    original = source.read_text()
    path, record, state = load_saved_extraction(source)
    result = run_saved_validation(
        state, record, path, tmp_path / "new", InterruptedModel(), SavedSearch()
    )
    assert result["status"] == "interrupted"
    assert json.loads((tmp_path / "new" / "trace.json").read_text())["status"] == "interrupted"
    assert source.read_text() == original
