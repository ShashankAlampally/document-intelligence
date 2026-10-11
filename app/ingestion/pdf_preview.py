"""Save actual PDF extraction as JSON and readable text for manual inspection."""

import argparse
from pathlib import Path

from app.ingestion.discovery import discover_bid_files
from app.ingestion.pdf_parser import parse_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to a PDF file")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("Output must use a .json extension")
    path = args.pdf.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        parser.error(f"Expected an existing PDF file: {path}")
    files = discover_bid_files(path.parent)
    document = parse_pdf(next(file for file in files if file.file_path == path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    sections = [f"File: {document.source.file_name}", f"Pages: {document.page_count}"]
    for number in range(1, (document.page_count or 0) + 1):
        sections.append(f"\n=== PAGE {number} ===")
        sections.extend(block.text for block in document.text_blocks if block.page_number == number)
        for table in document.tables:
            if table.page_number == number:
                sections.append("\nTABLE (headers are retained as rows when not identified):")
                sections.extend(" | ".join(cell or "" for cell in row) for row in table.rows)
        for image in document.images:
            if image.page_number == number:
                sections.append(f"IMAGE: {image.name}, bbox={image.bbox}; no OCR performed")
    sections.append("\nISSUES:")
    sections.extend(
        f"Page {issue.page_number}: {issue.code}: {issue.message}" for issue in document.issues
    )
    if not document.issues:
        sections.append("None recorded. This does not guarantee complete extraction.")
    text_path = args.output.with_suffix(".txt")
    text_path.write_text("\n".join(sections), encoding="utf-8")
    print(
        f"Pages: {document.page_count}; text blocks: {len(document.text_blocks)}; "
        f"tables: {len(document.tables)}; images: {len(document.images)}; "
        f"issues: {len(document.issues)}"
    )
    print(f"JSON: {args.output}\nReadable text: {text_path}")
    if any(issue.severity == "error" for issue in document.issues):
        parser.exit(status=1)


if __name__ == "__main__":
    main()
