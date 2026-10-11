"""Manually inspect preparation: run with python tests/inspect_preparation.py.

This is a demonstration script, not an automated pytest test. It saves no files.
"""

import argparse
import sys
from pathlib import Path

# Direct execution adds tests/ to sys.path; make project imports available too.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.cleaner import clean_text  # noqa: E402
from app.ingestion.pipeline import parse_folder  # noqa: E402
from app.ingestion.preparation import prepare_documents  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "folder",
        nargs="?",
        type=Path,
        default=PROJECT_ROOT / "Assignment-Data-Statements (AI Engineer-Emplay Inc)" / "Bid2",
        help="Folder to parse; defaults to the assignment's Bid2 folder",
    )
    parser.add_argument("--file", default="PORFP_-_Dell_Laptop_Final.pdf", help="File to inspect")
    parser.add_argument("--page", type=int, default=2, help="PDF page to inspect (default: 2)")
    args = parser.parse_args()
    try:
        parsed = parse_folder(args.folder)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    prepared = prepare_documents(parsed)
    matches = [
        (raw, clean) for raw, clean in zip(parsed, prepared) if raw.source.file_name == args.file
    ]
    if len(matches) != 1:
        parser.error("Expected one matching file; use --file to choose a unique filename")
    raw, clean = matches[0]
    before = [block.text for block in raw.text_blocks if block.page_number == args.page]
    after = [block.text for block in clean.text_blocks if block.page_number == args.page]
    if not before:
        parser.error(f"No extracted PDF text on page {args.page}; review the file's parsing issues")
    print(f"Processed {len(parsed)} files; inspecting {raw.source.file_name}, page {args.page}")
    print("\n=== ACTUAL CONTENT: BEFORE CLEANING ===")
    print("\n".join(before))
    print("\n=== ACTUAL CONTENT: AFTER CLEANING ===")
    print("\n".join(after))
    print(f"\nActual text changed: {before != after}")
    example = "Delivery   within\t45 days.\n\n\nInvoice   within 10 days."
    print("\n=== DEMONSTRATION INPUT (not extracted from the PDF) ===")
    print("Before:", repr(example))
    print("After: ", repr(clean_text(example)))
    print("\nNo files saved. Original parsed data is unchanged.")


if __name__ == "__main__":
    main()
