"""Read saved HTML into section-referenced text and tables without network access."""

import logging

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from app.ingestion.html_tables import extract_html_table
from app.ingestion.table_identity import assign_table_ids
from app.schemas.content import TextBlock
from app.schemas.documents import ParsedDocument, ParsingIssue
from app.schemas.files import FileRecord
from app.schemas.metadata import SourceMetadata

logger = logging.getLogger(__name__)
HEADINGS = {f"h{number}" for number in range(1, 7)}


def _issue(document: ParsedDocument, code: str, message: str, severity: str = "warning"):
    document.issues.append(ParsingIssue(code=code, message=message, severity=severity))
    logger.warning("%s code=%s: %s", document.source.file_name, code, message)


def _extract_content(root: Tag, document: ParsedDocument) -> None:
    heading = None
    number = 1
    lines: list[str] = []

    def flush() -> None:
        if lines:
            document.text_blocks.append(
                TextBlock(section=f"section-{number}", heading=heading, text="\n".join(lines))
            )
            lines.clear()

    for element in root.descendants:
        if isinstance(element, Tag):
            if element.name in HEADINGS:
                flush()
                number += 1
                heading = element.get_text(" ", strip=True) or None
            elif element.name == "table":
                try:
                    table = extract_html_table(element, f"section-{number}")
                    if table:
                        document.tables.append(table)
                except Exception as error:
                    _issue(document, "table_extraction_failed", str(error))
        elif isinstance(element, NavigableString) and not isinstance(element, Comment):
            text = " ".join(str(element).split())
            if text:
                lines.append(text)
    flush()


def parse_html(file: FileRecord) -> ParsedDocument:
    """Decode saved bytes, tolerate imperfect markup, and keep source metadata.

    Section IDs follow heading order, not invented browser page numbers. Table
    text also remains in text blocks, just as it does in our current PDF parser.
    """
    if file.file_type != "html":
        raise ValueError("parse_html expects an HTML file record")
    document = ParsedDocument(source=SourceMetadata(**file.model_dump()))
    try:
        data = file.file_path.read_bytes()
    except OSError as error:
        _issue(document, "unreadable_file", str(error), "error")
        return document
    try:
        soup = BeautifulSoup(data, "html.parser")
        if soup.contains_replacement_characters:
            _issue(document, "encoding_replacements", "Some bytes could not be decoded faithfully")
        for element in list(soup.select("head, script, style, template, [hidden]")):
            if element.parent is not None:
                element.decompose()
        root = soup.body or soup
        if root.find("img"):
            _issue(
                document, "image_content_not_read", "HTML image contents are not read or fetched"
            )
        _extract_content(root, document)
        if not document.text_blocks and not document.tables:
            _issue(document, "no_text_extracted", "No readable text or tables in the saved HTML")
    except Exception as error:
        _issue(document, "document_read_failed", str(error), "error")
    assign_table_ids(document)
    return document
