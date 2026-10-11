"""Locate embedded images, including images on pages with extractable text."""

from pymupdf import Page

from app.schemas.content import ImageRegion


def extract_image_regions(page: Page, page_number: int) -> list[ImageRegion]:
    return [
        ImageRegion(
            page_number=page_number,
            name=f"image-{index}",
            bbox=tuple(image["bbox"]),
        )
        for index, image in enumerate(page.get_image_info(), start=1)
    ]
