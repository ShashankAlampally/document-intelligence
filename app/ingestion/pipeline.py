"""Process every supported file in a folder through its format-specific parser."""

import logging
from pathlib import Path

from app.ingestion.discovery import discover_bid_files
from app.ingestion.document_metadata import label_document
from app.ingestion.html_parser import parse_html
from app.ingestion.pdf_parser import parse_pdf
from app.schemas.documents import ParsedDocument, ParsingIssue
from app.schemas.metadata import SourceMetadata

logger = logging.getLogger(__name__)


def parse_folder(folder_path: str | Path) -> list[ParsedDocument]:
    """Return documents in relative-path order, with one shared discovery ID.

    Folder discovery errors are raised to the caller. A file's parsing failure
    becomes an error document so other files can still be processed. Nothing is
    saved here; a preview command or later application layer chooses persistence.
    """
    records = discover_bid_files(folder_path)
    documents = []
    for record in records:
        try:
            parser = parse_pdf if record.file_type == "pdf" else parse_html
            document = parser(record)
        except Exception as error:
            logger.exception("Unexpected parser failure for %s", record.relative_path)
            document = ParsedDocument(
                source=SourceMetadata(**record.model_dump()),
                issues=[
                    ParsingIssue(
                        code="parser_failed",
                        message=str(error) or type(error).__name__,
                        severity="error",
                    )
                ],
            )
        documents.append(label_document(document))
    return documents
