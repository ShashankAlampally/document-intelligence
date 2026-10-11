"""Persistent extraction progress and explicit resume for the single-server website."""

import asyncio
import json
from uuid import uuid4

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from app.api.workspace.extraction_recovery import SavedModel, SavedSearch
from app.api.workspace.files import save_json
from app.api.workspace.queries import query_tool
from app.api.workspace.sources import source_passage


class ExtractionJobs:
    def __init__(self, service):
        self.service = service
        self.directory = service.settings.storage_dir / "extraction-jobs"
        self.tasks = {}

    def path(self, job_id):
        return self.directory / str(job_id) / "job.json"

    def save(self, record):
        save_json(self.path(record["id"]), json.dumps(record, ensure_ascii=False))

    def read(self, job_id):
        path = self.path(job_id)
        if not path.exists():
            raise HTTPException(404, "Extraction job not found")
        return json.loads(path.read_text())

    async def start(self, query):
        if len(query.discovery_ids) != 1:
            raise HTTPException(422, "Select one folder for extraction")
        await run_in_threadpool(self.service.runtime.require_uploads, query.discovery_ids)
        record = dict(
            id=str(uuid4()),
            status="running",
            detail="Queued for extraction",
            completed_fields=0,
            fields={},
            query=query.model_dump(mode="json"),
            configuration=self.configuration(),
        )
        self.save(record)
        self.launch(record)
        return self.public(record)

    def launch(self, record):
        job_id = record["id"]
        task = asyncio.create_task(self.execute(record))
        self.tasks[job_id] = task
        task.add_done_callback(lambda finished: self.tasks.pop(job_id, None))

    async def get(self, job_id):
        record = self.read(job_id)
        if record["status"] in {"running", "waiting"} and str(job_id) not in self.tasks:
            record.update(status="paused", detail="Server restarted. Resume saved extraction.")
            self.save(record)
        return self.public(record)

    async def resume(self, job_id):
        record = self.read(job_id)
        if record.get("configuration") != self.configuration():
            raise HTTPException(409, "Extraction settings changed. Start a new extraction job.")
        if record["status"] == "completed" or str(job_id) in self.tasks:
            return self.public(record)
        record.update(status="running", detail="Resuming saved steps")
        self.save(record)
        self.launch(record)
        return self.public(record)

    def public(self, record):
        return {
            key: value for key, value in record.items() if key not in {"query", "configuration"}
        }

    def configuration(self):
        settings = self.service.settings
        return {
            "model": settings.llm_model,
            "max_tokens": settings.llm_max_tokens,
            "collection": settings.vector_collection,
        }

    async def execute(self, record):
        try:
            async with self.service.worker:
                await run_in_threadpool(self.run, record)
        except Exception as error:
            record.update(
                status="paused",
                detail=f"Extraction paused ({type(error).__name__}). "
                "Completed fields are saved. Resume later.",
            )
            self.save(record)

    def run(self, record):
        from app.api.workspace_contracts import SelectedDocumentQuery

        query = SelectedDocumentQuery.model_validate(record["query"])
        runtime = self.service.runtime
        runtime.require_uploads(query.discovery_ids)
        directory = self.path(record["id"]).parent

        def progress(detail, status="running"):
            record.update(detail=detail, status=status)
            self.save(record)

        def group_done(name, result):
            record["fields"].update(
                {k: v.model_dump(mode="json") for k, v in result.fields.items()}
            )
            record["completed_fields"] = len(record["fields"])
            progress(f"{record['completed_fields']}/20 draft fields saved; validation pending")

        def step_done(trace):
            save_json(directory / "trace.json", json.dumps(trace, ensure_ascii=False))
            progress("Validating and correcting saved draft fields")

        model = runtime.model
        limiter = getattr(model, "rate_limit", None)
        previous = getattr(limiter, "event_sink", None)

        def event(event):
            if event["stage"] == "groq_wait_start":
                progress("Waiting for model budget; completed fields are saved", "waiting")
            if event["stage"] in {"groq_wait_end", "groq_request_start"}:
                progress("Continuing model call")
            if previous:
                previous(event)

        if limiter is not None:
            limiter.event_sink = event
        try:
            result = extract_bid_fields(
                SavedModel(model, directory, "model", progress),
                {
                    "search_documents": SavedSearch(
                        query_tool(runtime, query), directory, "search", progress
                    )
                },
                on_group=group_done,
                on_step=step_done,
            )
        finally:
            if limiter is not None:
                limiter.event_sink = previous
        save_json(directory / "result.json", result.model_dump_json(indent=2))
        if result.error:
            progress(f"{result.error}. Completed fields saved; resume later.", "paused")
            return
        record["fields"] = {k: v.model_dump(mode="json") for k, v in result.fields.items()}
        sources = {s["chunk_id"]: s for field in result.fields.values() for s in field.sources}
        record["reply"] = dict(
            answer="\n".join(
                f"{k}: {v.value or v.notes or 'Not found in documents'}"
                for k, v in result.fields.items()
            ),
            sources=[source_passage(s).model_dump(mode="json") for s in sources.values()],
        )
        record["completed_fields"] = len(result.fields)
        progress("Extraction and validation completed", "completed")
