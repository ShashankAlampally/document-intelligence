"""Save one upload safely before request-owned streams are closed."""

import shutil
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile

from app.config import Settings


def validate_names(files: list[UploadFile]) -> None:
    if not files:
        raise HTTPException(422, "Select at least one document")
    names = set()
    roots = set()
    for file in files:
        name = file.filename or ""
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or "\x00" in name
            or ":" in name
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            raise HTTPException(422, "Use safe folder-relative filenames")
        if path.suffix.lower() not in {".pdf", ".html", ".htm"}:
            raise HTTPException(422, "Only PDF, HTML and HTM files are supported")
        if name in names:
            raise HTTPException(422, "Duplicate relative filenames")
        names.add(name)
        if len(path.parts) > 1:
            roots.add(path.parts[0])
    if len(roots) > 1 or (roots and any(len(PurePosixPath(name).parts) == 1 for name in names)):
        raise HTTPException(422, "Upload one folder per request")


async def save_folder(files: list[UploadFile], settings: Settings, job_id: UUID) -> Path:
    validate_names(files)
    if len(files) > settings.upload_max_files:
        raise HTTPException(413, "Too many documents in this folder")
    base = settings.storage_dir / "uploads" / str(job_id)
    first = PurePosixPath(files[0].filename)
    folder = base / (first.parts[0] if len(first.parts) > 1 else "Uploaded documents")
    total = 0
    try:
        for file in files:
            path = PurePosixPath(file.filename)
            relative = Path(*path.parts[1:]) if len(first.parts) > 1 else Path(path.name)
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            with target.open("xb") as output:
                while data := await file.read(1024 * 1024):
                    size += len(data)
                    total += len(data)
                    if size > settings.upload_max_file_bytes or total > settings.upload_max_bytes:
                        raise HTTPException(413, "Folder or document exceeds the upload size limit")
                    output.write(data)
        return folder
    except BaseException:
        shutil.rmtree(base, ignore_errors=True)
        raise


def save_json(path: Path, content: str) -> None:
    """Replace a record atomically so polling never reads half-written JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}-{uuid4()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
