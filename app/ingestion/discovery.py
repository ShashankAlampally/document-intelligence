"""Discover supported files without reading their contents."""

import os
from pathlib import Path
from uuid import uuid4

from app.schemas.files import FileRecord

SUPPORTED_FORMATS = {".pdf": "pdf", ".html": "html", ".htm": "html"}


def _raise_walk_error(error: OSError) -> None:
    """Report inaccessible folders rather than returning an incomplete list."""
    raise error


def discover_bid_files(folder_path: str | Path) -> list[FileRecord]:
    """Return sorted file records with one new UUID shared by this discovery run.

    Relative input paths resolve from the caller's working directory. Subfolders
    are included; symbolic links and unsupported file formats are skipped.
    """
    folder = Path(folder_path).expanduser().resolve()
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Expected a folder: {folder}")

    discovery_id = uuid4()
    records = []
    for directory, _, file_names in os.walk(folder, onerror=_raise_walk_error):
        for file_name in file_names:
            path = Path(directory) / file_name
            file_type = SUPPORTED_FORMATS.get(path.suffix.lower())
            if file_type is None or path.is_symlink() or not path.is_file():
                continue
            records.append(
                FileRecord(
                    discovery_id=discovery_id,
                    folder_name=folder.name,
                    file_name=path.name,
                    relative_path=path.relative_to(folder),
                    file_path=path,
                    file_type=file_type,
                )
            )

    if not records:
        raise ValueError(f"No supported PDF or HTML files found in: {folder}")
    return sorted(records, key=lambda record: record.relative_path.as_posix())
