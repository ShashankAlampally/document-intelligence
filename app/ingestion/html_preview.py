"""Save HTML extraction as JSON and readable text for manual inspection."""

import argparse
from pathlib import Path

from app.ingestion.discovery import discover_bid_files
from app.ingestion.html_parser import parse_html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="Path to a saved HTML file")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("Output must use a .json extension")
    path = args.html.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".html", ".htm"}:
        parser.error(f"Expected an existing HTML file: {path}")
    files = discover_bid_files(path.parent)
    document = parse_html(next(file for file in files if file.file_path == path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    sections = [f"File: {document.source.file_name}"]
    for block in document.text_blocks:
        sections.append(f"\n=== {block.section}: {block.heading or 'Untitled'} ===\n{block.text}")
    for table in document.tables:
        sections.append(f"\nTABLE: {table.section}; {table.caption or 'No caption'}")
        sections.extend(" | ".join(cell or "" for cell in row) for row in table.rows)
    sections.append("\nISSUES:")
    sections.extend(f"{issue.code}: {issue.message}" for issue in document.issues)
    if not document.issues:
        sections.append("None recorded. This does not guarantee complete extraction.")
    text_path = args.output.with_suffix(".txt")
    text_path.write_text("\n".join(sections), encoding="utf-8")
    print(
        f"Text blocks: {len(document.text_blocks)}; tables: {len(document.tables)}; "
        f"issues: {len(document.issues)}"
    )
    print(f"JSON: {args.output}\nReadable text: {text_path}")
    if any(issue.severity == "error" for issue in document.issues):
        parser.exit(status=1)


if __name__ == "__main__":
    main()
