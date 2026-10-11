"""Basic file records returned by folder discovery."""

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FileRecord(BaseModel):
    discovery_id: UUID
    folder_name: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    relative_path: Path
    file_path: Path
    file_type: Literal["pdf", "html"]
