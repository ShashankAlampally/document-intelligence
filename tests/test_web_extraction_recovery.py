"""Offline checks for persistent operation replay and extraction job recovery."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.workspace.extraction_jobs import ExtractionJobs
from app.api.workspace.extraction_recovery import SavedModel, SavedSearch


def test_successful_calls_replayed_after_recreating_wrapper(tmp_path):
    class Model:
        calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            return {"message": {"content": '{"value":30}'}, "finish_reason": "stop"}

    model = Model()
    first = SavedModel(model, tmp_path, "model", lambda detail: None)
    answer = first.complete([{"role": "user", "content": "quantity"}])
    resumed = SavedModel(model, tmp_path, "model", lambda detail: None)
    assert resumed.complete([{"role": "user", "content": "quantity"}]) == answer
    assert model.calls == 1
    resumed.complete([{"role": "user", "content": "different question"}])
    assert model.calls == 2


def test_failed_model_call_is_retried_not_cached(tmp_path):
    class Model:
        calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("quota exhausted")
            return {"message": {"content": "{}"}}

    model = Model()
    wrapper = SavedModel(model, tmp_path, "model", lambda detail: None)
    with pytest.raises(RuntimeError):
        wrapper.complete([{"role": "user", "content": "test"}])
    assert not list(tmp_path.glob("model-*.json"))
    wrapper.complete([{"role": "user", "content": "test"}])
    assert model.calls == 2


def test_search_evidence_is_frozen_for_resume(tmp_path):
    calls = []
    search = SimpleNamespace(run=lambda args: calls.append(args) or [{"text": "30 laptops"}])
    wrapper = SavedSearch(search, tmp_path, "search", lambda detail: None)
    assert wrapper.run({"query": "quantity"}) == wrapper.run({"query": "quantity"})
    assert len(calls) == 1


def test_server_restart_preserves_partial_fields(tmp_path):
    service = SimpleNamespace(
        settings=SimpleNamespace(
            storage_dir=tmp_path, llm_model="test", llm_max_tokens=100, vector_collection="test"
        )
    )
    jobs = ExtractionJobs(service)
    job_id = str(uuid4())
    jobs.save(
        dict(
            id=job_id,
            status="waiting",
            completed_fields=3,
            fields={"Product": {"value": "30 laptops"}},
            query={},
        )
    )
    record = asyncio.run(jobs.get(job_id))
    assert record["status"] == "paused"
    assert record["completed_fields"] == 3
    assert record["fields"]["Product"]["value"] == "30 laptops"
    assert "query" not in record


def test_paused_job_resumes_without_discarding_fields(tmp_path):
    jobs = ExtractionJobs(
        SimpleNamespace(
            settings=SimpleNamespace(
                storage_dir=tmp_path, llm_model="test", llm_max_tokens=100, vector_collection="test"
            )
        )
    )
    job_id = str(uuid4())
    jobs.save(
        dict(
            id=job_id,
            status="paused",
            completed_fields=3,
            fields={"Product": {}},
            query={},
            configuration=jobs.configuration(),
        )
    )
    launched = []
    jobs.launch = launched.append
    record = asyncio.run(jobs.resume(job_id))
    assert record["status"] == "running"
    assert record["completed_fields"] == 3
    assert len(launched) == 1
