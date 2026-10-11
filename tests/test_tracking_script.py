"""The CLI preserves prior results and removes stale answers before a retry."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.extraction.models.fields import ExtractedField, ExtractionResult
from app.config import Settings
from scripts import track_extraction


@pytest.mark.parametrize("failure", [False, True])
def test_resumed_group_replaces_only_its_fields_and_preserves_original(
    tmp_path, monkeypatch, failure
):
    identity = uuid4()
    old = dict(
        discovery_id=str(identity),
        status="completed",
        trace=[],
        fields={
            "Bid Number": dict(value="old", sources=[], confidence=0, notes=None),
            "Title": dict(value="old title", sources=[], confidence=0, notes=None),
            "Due Date": dict(value="old date", sources=[], confidence=0, notes=None),
            "Installation": dict(value="keep this", sources=[], confidence=0, notes=None),
        },
    )
    prior = tmp_path / "prior.json"
    original = json.dumps(old)
    prior.write_text(original)
    settings = Settings(_env_file=None, output_dir=tmp_path / "outputs")
    monkeypatch.setattr(track_extraction, "Settings", lambda: settings)
    store = SimpleNamespace(
        list_chunks=lambda filters: ["stored"],
        info=SimpleNamespace(model_dump=lambda **kwargs: {"dimensions": 1024}),
    )
    monkeypatch.setattr(track_extraction, "ChromaVectorStore", lambda *args: store)
    monkeypatch.setattr(track_extraction, "LocalEmbeddingProvider", lambda settings: None)
    monkeypatch.setattr(track_extraction, "GroqModel", lambda settings: object())
    monkeypatch.setattr(
        track_extraction, "SearchTool", lambda *args: SimpleNamespace(discovery_ids=[identity])
    )

    def extract(model, tools, names, **kwargs):
        if failure:
            return ExtractionResult(status="error", error="Test failure")
        return ExtractionResult(
            status="completed",
            fields={
                name: ExtractedField(value=f"new {name}", sources=[], confidence=0, notes=None)
                for name in names
            },
        )

    monkeypatch.setattr(track_extraction, "extract_field_group", extract)
    monkeypatch.setattr(
        "sys.argv", ["track", str(identity), "--resume-from", str(prior), "--group", "bid_details"]
    )
    if failure:
        with pytest.raises(SystemExit):
            track_extraction.main()
    else:
        track_extraction.main()
    output = next(settings.output_dir.glob("pipeline-*/fields.json"))
    saved = json.loads(output.read_text())
    assert saved["fields"]["Installation"]["value"] == "keep this"
    assert prior.read_text() == original
    if failure:
        assert saved["status"] == "error"
        assert "Bid Number" not in saved["fields"]
    else:
        assert saved["fields"]["Bid Number"]["value"] == "new Bid Number"
        assert saved["status"] == "completed"


def test_full_tracking_uses_combined_validation_and_saves_the_report(tmp_path):
    from test_combined_extraction_validation import CombinedModel
    from test_extraction_agent import FakeSearch

    from app.agents.extraction.models.field_catalog import FIELD_GROUPS
    from scripts.track_combined_extraction import track_combined_extraction

    model = CombinedModel()
    record = dict(discovery_id=str(uuid4()), status="running", fields={}, trace=[], error=None)
    track_combined_extraction(model, FakeSearch(), FIELD_GROUPS, tmp_path, record)
    assert record["status"] == "completed"
    assert len(model.calls) == 8
    assert len(record["fields"]) == 20
    assert len(record["validation_report"][0]["fields"]) == 20
    saved = json.loads((tmp_path / "fields.json").read_text())
    assert saved["validation_report"] == record["validation_report"]
    report = (tmp_path / "report.md").read_text()
    assert "Combined validation" in report
    assert "Model attempts recorded: 8" in report
