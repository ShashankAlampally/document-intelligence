"""Compare local PDF libraries on selected pages; no embeddings or Groq calls."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import pdfplumber

from app.ingestion.discovery import discover_bid_files
from app.ingestion.pdf_parser import parse_pdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.pdf.expanduser().resolve()
    record = next(file for file in discover_bid_files(path.parent) if file.file_path == path)
    started = perf_counter()
    document = parse_pdf(record)
    elapsed = perf_counter() - started
    if any(number < 1 or number > (document.page_count or 0) for number in args.pages):
        parser.error("Page numbers must exist in the PDF")
    pages = []
    with pdfplumber.open(path) as old:
        for number in args.pages:
            started = perf_counter()
            page = old.pages[number - 1]
            text = page.extract_text() or ""
            tables = page.extract_tables()
            old_elapsed = perf_counter() - started
            new_text = "\n".join(
                block.text for block in document.text_blocks if block.page_number == number
            )
            new_tables = [
                table.model_dump(mode="json")
                for table in document.tables
                if table.page_number == number
            ]
            pages.append(
                {
                    "page": number,
                    "pdfplumber": {"text": text, "tables": tables, "elapsed_seconds": old_elapsed},
                    "pymupdf": {"text": new_text, "tables": new_tables},
                }
            )
            print(
                f"Page {number}: pdfplumber chars={len(text)}, tables={len(tables)}; "
                f"PyMuPDF chars={len(new_text)}, tables={len(new_tables)}"
            )
    result = {
        "file": str(path),
        "pymupdf_full_file_seconds": elapsed,
        "issues": [issue.model_dump() for issue in document.issues],
        "pages": pages,
        "comparison_note": "pdfplumber uses library defaults without the old custom "
        "borderless fallback. Character counts do not measure accuracy.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PyMuPDF full file: {elapsed:.2f}s\nSaved: {args.output}")


if __name__ == "__main__":
    main()
