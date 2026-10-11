"""Processing-status route, independently connectable to a job service."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.workspace_contracts import WORKSPACE_RESPONSES, ProcessingJob
from app.api.workspace_service import WorkspaceService, get_workspace_service

router = APIRouter(prefix="/api/jobs", tags=["folder processing"])


@router.get("/{job_id}", response_model=ProcessingJob, responses=WORKSPACE_RESPONSES)
async def get_folder_processing_status(
    job_id: UUID, service: WorkspaceService = Depends(get_workspace_service)
) -> ProcessingJob:
    return await service.get_job(job_id)
