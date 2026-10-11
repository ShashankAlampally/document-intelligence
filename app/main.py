"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.document_query_routes import router as document_query_router
from app.api.folder_upload_routes import router as folder_upload_router
from app.api.frontend_static import mount_frontend
from app.api.health import router as health_router
from app.api.processing_status_routes import router as processing_status_router
from app.api.workspace.service import ConnectedWorkspaceService
from app.api.workspace_service import WorkspaceNotConnected
from app.config import Settings


def create_app() -> FastAPI:
    settings = Settings()
    service = ConnectedWorkspaceService(settings)

    @asynccontextmanager
    async def lifespan(application):
        try:
            yield
        finally:
            await application.state.workspace_service.close()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Upload bid folders, search passages, and ask cited questions.",
        lifespan=lifespan,
    )
    application.state.workspace_service = service
    application.include_router(health_router)
    application.include_router(folder_upload_router)
    application.include_router(processing_status_router)
    application.include_router(document_query_router)

    @application.exception_handler(WorkspaceNotConnected)
    async def workspace_not_connected(request: Request, exc: WorkspaceNotConnected) -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={
                "code": "workspace_not_connected",
                "detail": "Route is available, but document processing/search services "
                "are not connected yet.",
            },
        )

    mount_frontend(application, settings.frontend_dist_dir)
    return application
