"""Format chunks for inspection without mixing them with raw table previews."""

from app.schemas.chunks import ChunkedDocument


def format_chunks(result: ChunkedDocument) -> str:
    document = result.document
    lines = [
        f"\n=== FILE: {document.source.relative_path} ===",
        f"Discovery ID: {document.source.discovery_id}",
        f"Text chunks: {len(result.chunks)}; retained tables: {len(document.tables)}; "
        f"retained PDF images: {len(document.images)}",
    ]
    for number, chunk in enumerate(result.chunks, start=1):
        lines.extend(
            [
                f"\n--- CHUNK {number}: {chunk.chunk_id} ---",
                f"Page: {chunk.page_number}; section: {chunk.section}; "
                f"block: {chunk.block_index}; characters: [{chunk.start_char}, {chunk.end_char})",
                f"Type: {chunk.content_type}; method: {chunk.extraction_method}; "
                f"length: {len(chunk.text)}",
                f"Heading: {chunk.heading}",
                chunk.text,
            ]
        )
    lines.append("\nISSUES:")
    lines.extend(
        f"{issue.severity}: page={issue.page_number}: {issue.code}: {issue.message}"
        for issue in document.issues
    )
    if not document.issues:
        lines.append("None recorded. This does not guarantee complete extraction.")
    return "\n".join(lines)
