"""Folder-upload HTTP boundary. Validates names and delegates saving/indexing."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.workspace.files import validate_names
from app.api.workspace_contracts import WORKSPACE_RESPONSES, ProcessingJob
from app.api.workspace_service import WorkspaceService, get_workspace_service
from app.schemas.search import IndexReport

router = APIRouter(prefix="/api/sessions", tags=["folder processing"])


@router.post("", response_model=ProcessingJob, status_code=202, responses=WORKSPACE_RESPONSES)
async def upload_bid_folder(
    files: list[UploadFile] = File(
        ..., description="PDF/HTML files with folder-relative filenames"
    ),
    service: WorkspaceService = Depends(get_workspace_service),
) -> ProcessingJob:
    """Validate upload names, then hand off to the replaceable service boundary."""
    try:
        validate_names(files)
        return await service.start_folder(files)
    finally:
        for file in files:
            await file.close()


@router.get("/{discovery_id}", response_model=IndexReport, responses=WORKSPACE_RESPONSES)
async def get_indexed_folder(
    discovery_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
) -> IndexReport:
    return await service.get_upload(discovery_id)
