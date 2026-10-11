"""Replaceable HTTP service interface; the app installs its connected adapter."""

from uuid import UUID

from fastapi import Request, UploadFile

from app.api.workspace_contracts import (
    DocumentQuery,
    DocumentReply,
    ProcessingJob,
    SelectedDocumentQuery,
)
from app.schemas.search import IndexReport


class WorkspaceNotConnected(Exception):
    """Raised until an adapter to ingestion/search/agents is installed."""


class WorkspaceService:
    """Replace this dependency with a core adapter without changing HTTP routes.

    start_folder must consume/save uploads before returning, enqueue processing,
    and return a job ID. A ready job must identify its isolated document session.
    The adapter owns session lookup, storage, limits, job lifecycle and cleanup.
    """

    async def start_folder(self, files: list[UploadFile]) -> ProcessingJob:
        raise WorkspaceNotConnected

    async def get_upload(self, discovery_id: UUID) -> IndexReport:
        raise WorkspaceNotConnected

    async def get_job(self, job_id: UUID) -> ProcessingJob:
        raise WorkspaceNotConnected

    async def ask(self, session_id: UUID, query: DocumentQuery) -> DocumentReply:
        raise WorkspaceNotConnected

    async def search(self, session_id: UUID, query: DocumentQuery) -> DocumentReply:
        raise WorkspaceNotConnected

    async def ask_selected(self, query: SelectedDocumentQuery) -> DocumentReply:
        if len(query.discovery_ids) == 1:
            return await self.ask(
                query.discovery_ids[0],
                DocumentQuery.model_validate(query.model_dump(exclude={"discovery_ids"})),
            )
        raise WorkspaceNotConnected

    async def search_selected(self, query: SelectedDocumentQuery) -> DocumentReply:
        if len(query.discovery_ids) == 1:
            return await self.search(
                query.discovery_ids[0],
                DocumentQuery.model_validate(query.model_dump(exclude={"discovery_ids"})),
            )
        raise WorkspaceNotConnected


def get_workspace_service(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service
