"""Text and table content with locations in the original document."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContentLocation(BaseModel):
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None


class TextBlock(ContentLocation):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)
    heading: str | None = None


class TableBlock(ContentLocation):
    table_id: UUID | None = None
    # None preserves empty/merged cells; headers may be absent in the source.
    headers: list[str | None] = Field(default_factory=list)
    rows: list[list[str | None]] = Field(min_length=1)
    caption: str | None = None

    @model_validator(mode="after")
    def check_columns(self) -> "TableBlock":
        width = len(self.headers) if self.headers else len(self.rows[0])
        if width == 0 or any(len(row) != width for row in self.rows):
            raise ValueError("Table rows must have a consistent, nonzero column count")
        return self


class ImageRegion(BaseModel):
    """An embedded image occurrence; its contents have not been read by OCR.

    Coordinates are PDF points, measured from the page's top-left corner.
    """

    page_number: int = Field(ge=1)
    name: str
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def check_bounds(self) -> "ImageRegion":
        left, top, right, bottom = self.bbox
        if right <= left or bottom <= top:
            raise ValueError("Image bounds must have positive width and height")
        return self
