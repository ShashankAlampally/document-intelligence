"""Shared search chunk contract for text and future table/OCR producers."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.content import ContentLocation
from app.schemas.metadata import SourceMetadata
from app.schemas.prepared import PreparedDocument


class ChunkSettings(BaseModel):
    max_chars: int = Field(default=2000, ge=1)
    overlap_chars: int = Field(default=200, ge=0)

    structure_aware: bool = False

    @model_validator(mode="after")
    def check_overlap(self) -> "ChunkSettings":
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        return self


class Chunk(ContentLocation):
    chunk_id: UUID
    source: SourceMetadata
    content_type: Literal["text", "table"] = "text"
    extraction_method: Literal["native", "ocr"] = "native"
    text: str = Field(min_length=1)
    heading: str | None = None
    block_index: int = Field(ge=0)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    table_id: UUID | None = None
    table_row_start: int | None = Field(default=None, ge=1)
    table_row_end: int | None = Field(default=None, ge=1)
    table_total_rows: int | None = Field(default=None, ge=1)
    table_headers: list[str | None] = Field(default_factory=list)
    table_rows: list[list[str | None]] = Field(default_factory=list)
    table_complete: bool | None = None
    source_chunk_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_provenance(self) -> "Chunk":
        if self.table_id is not None:
            if self.content_type != "table" or any(
                value is None
                for value in (self.table_row_start, self.table_row_end, self.table_total_rows)
            ):
                raise ValueError("Identified table chunks require row provenance")
            if not 1 <= self.table_row_start <= self.table_row_end <= self.table_total_rows:
                raise ValueError("Invalid table row range")
            if len(self.table_rows) != self.table_row_end - self.table_row_start + 1:
                raise ValueError("Table rows must match the declared row range")
            if self.table_complete and len(self.table_rows) != self.table_total_rows:
                raise ValueError("Complete table evidence must contain every row")
        if self.end_char - self.start_char != len(self.text):
            raise ValueError("Character range must match the chunk text length")
        if self.source.file_type == "pdf" and self.page_number is None:
            raise ValueError("PDF chunks require a page number")
        if self.source.file_type == "html" and (
            self.page_number is not None or self.section is None
        ):
            raise ValueError("HTML chunks require a section and no page number")
        return self


class ChunkedDocument(BaseModel):
    """Keep prepared evidence and issues alongside searchable chunks."""

    document: PreparedDocument
    settings: ChunkSettings
    chunks: list[Chunk] = Field(default_factory=list)
