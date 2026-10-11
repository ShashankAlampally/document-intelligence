"""Small persistent job records; successful IDs survive a server restart."""

from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from app.api.workspace.files import save_json
from app.api.workspace_contracts import ProcessingJob


class JobRecords:
    def __init__(self, storage_dir: Path):
        self.path = storage_dir / "jobs"

    def save(self, job: ProcessingJob) -> None:
        save_json(self.path / f"{job.id}.json", job.model_dump_json(indent=2))

    def get(self, job_id: UUID) -> ProcessingJob:
        path = self.path / f"{job_id}.json"
        if not path.is_file():
            raise HTTPException(404, "Processing job not found")
        return ProcessingJob.model_validate_json(path.read_text(encoding="utf-8"))
