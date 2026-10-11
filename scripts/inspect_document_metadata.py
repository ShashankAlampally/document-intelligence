"""Inspect document roles without embedding, indexing or making model calls."""

import argparse
from pathlib import Path

from app.ingestion.pipeline import parse_folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    try:
        documents = parse_folder(args.folder)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for document in documents:
        source = document.source
        print(f"{source.file_name}")
        print(f"  type={source.doc_type}; addendum_number={source.addendum_number}")
    print("No output files saved. The existing Chroma index is unchanged.")


if __name__ == "__main__":
    main()
