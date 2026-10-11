"""A document's source, extracted content, and parsing problems."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.content import ImageRegion, TableBlock, TextBlock
from app.schemas.metadata import SourceMetadata


class ParsingIssue(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: Literal["warning", "error"] = "warning"
    page_number: int | None = Field(default=None, ge=1)


class ParsedDocument(BaseModel):
    source: SourceMetadata
    page_count: int | None = Field(default=None, ge=1)
    text_blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    images: list[ImageRegion] = Field(default_factory=list)
    issues: list[ParsingIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_locations(self) -> "ParsedDocument":
        content = [*self.text_blocks, *self.tables, *self.images]
        if self.source.file_type == "html":
            if self.page_count is not None or any(
                item.page_number is not None for item in [*content, *self.issues]
            ):
                raise ValueError("HTML documents use section references, not PDF page numbers")
        elif any(item.page_number is None for item in content):
            raise ValueError("PDF content must include its physical page number")
        if self.page_count is not None and any(
            item.page_number is not None and item.page_number > self.page_count
            for item in [*content, *self.issues]
        ):
            raise ValueError("Content or issue page number exceeds the document page count")
        return self
