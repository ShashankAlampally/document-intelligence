"""Question and standalone search routes delegated to the connected service."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.workspace_contracts import (
    WORKSPACE_RESPONSES,
    DocumentQuery,
    DocumentReply,
    SelectedDocumentQuery,
)
from app.api.workspace_service import WorkspaceService, get_workspace_service

router = APIRouter(prefix="/api/sessions", tags=["document queries"])


@router.post("/extractions")
async def start_extraction(
    query: SelectedDocumentQuery, service: WorkspaceService = Depends(get_workspace_service)
):
    return await service.extractions.start(query)


@router.get("/extractions/{job_id}")
async def get_extraction(job_id: UUID, service: WorkspaceService = Depends(get_workspace_service)):
    return await service.extractions.get(job_id)


@router.post("/extractions/{job_id}/resume")
async def resume_extraction(
    job_id: UUID, service: WorkspaceService = Depends(get_workspace_service)
):
    return await service.extractions.resume(job_id)


@router.post("/{session_id}/ask", response_model=DocumentReply, responses=WORKSPACE_RESPONSES)
async def ask_bid_question(
    session_id: UUID,
    query: DocumentQuery,
    service: WorkspaceService = Depends(get_workspace_service),
) -> DocumentReply:
    return await service.ask(session_id, query)


@router.post("/{session_id}/search", response_model=DocumentReply, responses=WORKSPACE_RESPONSES)
async def search_bid_documents(
    session_id: UUID,
    query: DocumentQuery,
    service: WorkspaceService = Depends(get_workspace_service),
) -> DocumentReply:
    return await service.search(session_id, query)


@router.post("/ask", response_model=DocumentReply, responses=WORKSPACE_RESPONSES)
async def ask_selected_folders(
    query: SelectedDocumentQuery,
    service: WorkspaceService = Depends(get_workspace_service),
) -> DocumentReply:
    return await service.ask_selected(query)


@router.post("/search", response_model=DocumentReply, responses=WORKSPACE_RESPONSES)
async def search_selected_folders(
    query: SelectedDocumentQuery,
    service: WorkspaceService = Depends(get_workspace_service),
) -> DocumentReply:
    return await service.search_selected(query)
