"""Background folder jobs and off-thread queries for the single-server demo."""

import asyncio
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.workspace.files import save_folder
from app.api.workspace.jobs import JobRecords
from app.api.workspace.queries import agent_reply, search_reply
from app.api.workspace.runtime import PipelineRuntime
from app.api.workspace.saved_upload import load_saved_upload
from app.api.workspace_contracts import DocumentQuery, ProcessingJob, SelectedDocumentQuery
from app.api.workspace_service import WorkspaceService
from app.config import Settings


class ConnectedWorkspaceService(WorkspaceService):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.runtime = PipelineRuntime(settings)
        self.jobs = JobRecords(settings.storage_dir)
        self.tasks: dict[UUID, asyncio.Task] = {}
        self.worker = asyncio.Lock()

    async def start_folder(self, files: list[UploadFile]) -> ProcessingJob:
        job = ProcessingJob(id=uuid4(), status="processing")
        folder = await save_folder(files, self.settings, job.id)
        self.jobs.save(job)
        task = asyncio.create_task(self.process_folder(job, folder))
        self.tasks[job.id] = task
        task.add_done_callback(lambda finished: self.tasks.pop(job.id, None))
        return job

    async def process_folder(self, job, folder) -> None:
        try:
            async with self.worker:
                report = await run_in_threadpool(self.runtime.index, folder)
            issues = sum(len(file.issues) for file in report.files)
            self.jobs.save(
                ProcessingJob(
                    id=job.id,
                    status="ready",
                    discovery_id=report.discovery_id,
                    detail=f"Indexed {report.stored_chunks} chunks. {issues} parsing notices.",
                )
            )
        except Exception as error:
            detail = f"Indexing failed ({type(error).__name__}). "
            if isinstance(error, ValueError):
                detail += str(error)[:240]
            else:
                detail += "Review the files and server configuration."
            self.jobs.save(
                ProcessingJob(
                    id=job.id,
                    status="failed",
                    detail=detail,
                )
            )

    async def get_upload(self, discovery_id: UUID):
        return await run_in_threadpool(load_saved_upload, self.settings, discovery_id)

    async def get_job(self, job_id: UUID) -> ProcessingJob:
        job = self.jobs.get(job_id)
        if job.status == "processing" and job_id not in self.tasks:
            job = ProcessingJob(
                id=job_id,
                status="failed",
                detail=("Processing was interrupted by a server restart. Upload the folder again."),
            )
            self.jobs.save(job)
        return job

    async def ask(self, session_id: UUID, query: DocumentQuery):
        return await self.ask_selected(
            SelectedDocumentQuery(discovery_ids=[session_id], **query.model_dump())
        )

    async def search(self, session_id: UUID, query: DocumentQuery):
        return await self.search_selected(
            SelectedDocumentQuery(discovery_ids=[session_id], **query.model_dump())
        )

    async def execute_query(self, query, operation):
        async with self.worker:
            try:
                await run_in_threadpool(self.runtime.require_uploads, query.discovery_ids)
                return await run_in_threadpool(operation, self.runtime, query)
            except HTTPException:
                raise
            except Exception as error:
                raise HTTPException(
                    503,
                    (
                        f"Document service failed ({type(error).__name__}). "
                        "Check server configuration."
                    ),
                ) from error

    async def ask_selected(self, query: SelectedDocumentQuery):
        return await self.execute_query(query, agent_reply)

    async def search_selected(self, query: SelectedDocumentQuery):
        return await self.execute_query(query, search_reply)

    async def close(self) -> None:
        if self.tasks:
            await asyncio.gather(*list(self.tasks.values()))
