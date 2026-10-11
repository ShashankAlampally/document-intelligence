"""Label obvious document roles using filenames and opening headings."""

import re

from app.schemas.documents import ParsedDocument
from app.schemas.metadata import DocumentType, SourceMetadata


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", value)).lower().strip()


def _document_type(value: str) -> DocumentType:
    if re.search(r"\baffidavit\b", value):
        return "affidavit"
    if re.search(r"\baddendum\b", value):
        return "addendum"
    if re.search(r"\b(specs|specifications?)\b", value):
        return "specs"
    if re.search(r"\b(rfp|porfp)\b|\brequest for proposals?\b", value):
        return "rfp"
    return "unknown"


def classify_source(source: SourceMetadata, opening_text: str = "") -> SourceMetadata:
    """Preserve explicit labels; never infer document dates from bid deadlines.

    Filename signals take priority over opening text. Unknown PDFs remain unknown.
    Saved HTML is treated as a bid page in this assignment's input format.
    These are transparent heuristics, not guaranteed document classification.
    """
    filename = _normalize(source.file_name)
    opening = _normalize("\n".join(opening_text.splitlines()[:8]))
    doc_type = source.doc_type
    if doc_type == "unknown":
        doc_type = _document_type(filename)
        if doc_type == "unknown" and source.file_type == "html":
            doc_type = "bid_page"
        if doc_type == "unknown":
            # Opening role headings, rather than every mention in the document body.
            for line in opening_text.splitlines()[:8]:
                heading = _normalize(line)
                if re.match(
                    r"^(addendum|affidavit|specifications?|request for proposals?)\b", heading
                ):
                    doc_type = _document_type(heading)
                    break
    number = source.addendum_number
    if doc_type == "addendum" and number is None:
        pattern = r"\baddendum\s*(?:(?:no\.?|number|#)\s*)?(\d+)\b"
        match = re.search(pattern, filename) or re.search(pattern, opening)
        if match and int(match.group(1)) > 0:
            number = int(match.group(1))
    return SourceMetadata(
        **{**source.model_dump(), "doc_type": doc_type, "addendum_number": number}
    )


def label_document(document: ParsedDocument) -> ParsedDocument:
    opening = ""
    if document.text_blocks:
        opening = document.text_blocks[0].text
    source = classify_source(document.source, opening)
    return document.model_copy(update={"source": source})
