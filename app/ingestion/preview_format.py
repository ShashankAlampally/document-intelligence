"""Format folder extraction for human inspection without changing parsed data."""

from app.schemas.documents import ParsedDocument


def format_document(document: ParsedDocument) -> str:
    source = document.source
    lines = [
        f"\n=== FILE: {source.relative_path} ===",
        f"Folder: {source.folder_name}; discovery ID: {source.discovery_id}",
        f"Format: {source.file_type}; PDF pages: {document.page_count}",
    ]
    if source.file_type == "pdf":
        locations = range(1, (document.page_count or 0) + 1)
    else:
        locations = dict.fromkeys(
            item.section for item in [*document.text_blocks, *document.tables]
        )
    for location in locations:
        lines.append(f"\n--- {'PAGE' if source.file_type == 'pdf' else 'SECTION'} {location} ---")
        for block in document.text_blocks:
            if (block.page_number if source.file_type == "pdf" else block.section) == location:
                if block.heading:
                    lines.append(f"Heading: {block.heading}")
                lines.append(block.text)
        for table in document.tables:
            if (table.page_number if source.file_type == "pdf" else table.section) == location:
                lines.append(f"TABLE: {table.caption or '(no caption)'}")
                if table.headers:
                    lines.append(" | ".join(cell or "" for cell in table.headers))
                lines.extend(" | ".join(cell or "" for cell in row) for row in table.rows)
        for image in document.images:
            if image.page_number == location:
                lines.append(f"IMAGE: {image.name}, bbox={image.bbox}; no OCR performed")
    lines.append("\nISSUES:")
    lines.extend(
        f"{issue.severity}: page={issue.page_number}: {issue.code}: {issue.message}"
        for issue in document.issues
    )
    if not document.issues:
        lines.append("None recorded. This does not guarantee complete extraction.")
    return "\n".join(lines)
