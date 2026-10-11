"""Source details carried from discovery into document parsing."""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.files import FileRecord

DocumentType = Literal["bid_page", "rfp", "addendum", "specs", "affidavit", "unknown"]


class SourceMetadata(FileRecord):
    doc_type: DocumentType = "unknown"
    addendum_number: int | None = Field(default=None, ge=1)
    document_date: date | None = None
