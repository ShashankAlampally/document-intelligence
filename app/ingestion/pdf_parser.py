"""Read PDFs into source-preserving content and per-page extraction issues."""

import logging

import pymupdf
from pymupdf import Page

from app.ingestion.pdf_images import extract_image_regions
from app.ingestion.pdf_tables import extract_pdf_tables
from app.ingestion.table_identity import assign_table_ids
from app.schemas.content import TextBlock
from app.schemas.documents import ParsedDocument, ParsingIssue
from app.schemas.files import FileRecord
from app.schemas.metadata import SourceMetadata

logger = logging.getLogger(__name__)


def _add_issue(document: ParsedDocument, code: str, message: str, page: int | None) -> None:
    document.issues.append(ParsingIssue(code=code, message=message, page_number=page))
    logger.warning("%s page=%s code=%s: %s", document.source.file_name, page, code, message)


def _read_page(page: Page, number: int, document: ParsedDocument) -> None:
    try:
        text = (page.get_text("text", sort=True) or "").strip()
        if text:
            document.text_blocks.append(TextBlock(page_number=number, text=text))
        else:
            _add_issue(
                document,
                "no_text_extracted",
                "No extractable text. Review this page; OCR may be needed. "
                "It is not assumed blank.",
                number,
            )
    except Exception as error:
        _add_issue(document, "text_extraction_failed", str(error), number)

    # Independent operations preserve text when table/image extraction fails.
    try:
        document.tables.extend(extract_pdf_tables(page, number))
    except Exception as error:
        _add_issue(document, "table_extraction_failed", str(error), number)
    try:
        document.images.extend(extract_image_regions(page, number))
    except Exception as error:
        _add_issue(document, "image_detection_failed", str(error), number)


def parse_pdf(file: FileRecord) -> ParsedDocument:
    """Parse one discovered PDF; invalid formats are caller errors.

    Text includes table text where the library returns it. Images are locations,
    not OCR results. Document-role classification is handled in a later batch.
    """
    if file.file_type != "pdf":
        raise ValueError("parse_pdf expects a PDF file record")
    document = ParsedDocument(source=SourceMetadata(**file.model_dump()))
    try:
        pdf = pymupdf.open(file.file_path)
    except Exception as error:
        document.issues.append(
            ParsingIssue(code="unreadable_file", message=str(error), severity="error")
        )
        logger.error("Could not open %s: %s", file.file_name, error)
        return document

    try:
        with pdf:
            if not pdf.page_count:
                _add_issue(document, "empty_pdf", "PDF has no pages.", None)
                return document
            document.page_count = pdf.page_count
            for number, page in enumerate(pdf, start=1):
                try:
                    _read_page(page, number, document)
                except Exception as error:
                    _add_issue(document, "page_extraction_failed", str(error), number)
    except Exception as error:
        document.issues.append(
            ParsingIssue(code="document_read_failed", message=str(error), severity="error")
        )
        logger.error("Could not finish %s: %s", file.file_name, error)
    assign_table_ids(document)
    return document
