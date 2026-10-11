"""Tracking saves detailed failures, HTTP retries, waits and interrupted progress."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_extraction_groups import GroupModel
from test_groq_rate_limit import completion, failure, handler
from test_validation_batches import field, passage

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.models.fields import ExtractionDraft
from app.agents.extraction.nodes.validate_fields import validate_fields
from scripts.groq_event_summary import summarize_events
from scripts.pipeline_report import save_record
from scripts.pipeline_tracking import TrackingModel, TrackingSearch


def events(directory):
    return [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]


def test_search_failure_preserves_request_and_detailed_exception(tmp_path):
    search = SimpleNamespace(
        discovery_ids=["upload"], run=Mock(side_effect=ValueError("invalid discovery filter"))
    )
    with pytest.raises(ValueError):
        TrackingSearch(search, tmp_path).run({"query": "Delivery?", "field_name": "Delivery Date"})
    saved = events(tmp_path)
    assert [item["stage"] for item in saved] == ["search_input", "search_error"]
    assert saved[-1]["error_detail"] == "invalid discovery filter"
    assert saved[-1]["request"]["field_name"] == "Delivery Date"
    assert saved[-1]["search_id"] == 1
    assert all("timestamp_utc" in item for item in saved)


def test_model_events_include_http_attempts_retry_and_actual_wait(tmp_path):
    limiter, clock = handler()
    original = Mock()
    limiter.event_sink = original
    request = Mock(side_effect=[failure(headers={"retry-after": "2"}), completion(10)])

    def complete(messages, **kwargs):
        limiter.execute(request, 20)
        return {"message": {"content": "{}"}, "usage": {"total_tokens": 10}}

    model = TrackingModel(SimpleNamespace(rate_limit=limiter, complete=complete), tmp_path)
    model.complete(
        [{"role": "user", "content": "check"}],
        response_format={"json_schema": {"name": "field_validation"}},
    )
    saved = events(tmp_path)
    stages = [item["stage"] for item in saved]
    assert stages.count("groq_request_start") == 2
    assert "groq_request_error" in stages and "groq_retry" in stages
    assert stages.count("groq_wait_start") == stages.count("groq_wait_end") == 1
    assert all(item["call_id"] == 1 for item in saved)
    assert all(item["schema_name"] == "field_validation" for item in saved)
    assert limiter.event_sink is original
    assert original.call_count > 0
    assert clock.waits == [2]
    summary = summarize_events(tmp_path)
    assert summary["http_attempts"] == 2
    assert summary["observed_wait_seconds"] == 2
    assert summary["provider_errors"] == {"429": 1}
    assert summary["reported_tokens"] == 10


def test_exhausted_retry_records_provider_error_and_restores_event_sink(tmp_path):
    limiter, _ = handler(llm_rate_limit_retries=0)

    def complete(messages, **kwargs):
        limiter.execute(Mock(side_effect=failure()), 20)

    model = TrackingModel(SimpleNamespace(rate_limit=limiter, complete=complete), tmp_path)
    with pytest.raises(Exception):
        model.complete([{"role": "user", "content": "check"}])
    saved = events(tmp_path)
    assert any(item["stage"] == "groq_retry_stopped" for item in saved)
    assert saved[-1]["stage"] == "model_error"
    assert saved[-1]["status_code"] == 429
    assert "simulated failure" in saved[-1]["error_detail"]
    assert limiter.event_sink is None


def test_interrupted_wait_records_elapsed_time_and_model_interruption(tmp_path):
    limiter, clock = handler()
    limiter.cooldown_until = 10

    def sleep(duration):
        clock.now += 3
        raise KeyboardInterrupt()

    limiter.sleep = sleep

    def complete(messages, **kwargs):
        limiter.execute(lambda: completion(), 20)

    model = TrackingModel(SimpleNamespace(rate_limit=limiter, complete=complete), tmp_path)
    with pytest.raises(KeyboardInterrupt):
        model.complete([{"role": "user", "content": "check"}])
    saved = events(tmp_path)
    ended = next(item for item in saved if item["stage"] == "groq_wait_end")
    assert ended["interrupted"] is True and ended["elapsed_seconds"] == 3
    assert saved[-1]["error"] == "KeyboardInterrupt"
    assert summarize_events(tmp_path)["http_attempts"] == 0
    assert limiter.event_sink is None


def test_completed_validation_batch_is_saved_before_next_batch_interrupts(tmp_path):
    class InterruptedModel(GroupModel):
        def complete(self, messages, **kwargs):
            if self.calls:
                raise KeyboardInterrupt()
            return super().complete(messages, **kwargs)

    fields = [field("Title", ["one"]), field("Bid Number", ["two"])]
    state = ExtractionState(
        requested_fields=[item.name for item in fields],
        evidence=[passage("one", 6500), passage("two", 6500)],
        draft=ExtractionDraft(fields=fields),
    )
    record = dict(discovery_id="upload", status="running", fields={}, trace=[])

    def save_step(trace):
        record["trace"] = trace
        save_record(tmp_path, record)

    tracked = TrackingModel(InterruptedModel(), tmp_path)
    with pytest.raises(KeyboardInterrupt):
        validate_fields(state, tracked, on_step=save_step)
    saved = json.loads((tmp_path / "trace.json").read_text())
    assert len(saved["trace"]) == 1
    assert saved["trace"][0]["batch_index"] == 1
    assert saved["trace"][0]["output"]["fields"][0]["decision"] == "accepted"
    assert events(tmp_path)[-1]["error"] == "KeyboardInterrupt"
