"""Update an existing upload's document labels without reindexing it."""

import argparse
from uuid import UUID

from app.config import Settings
from app.search.chroma_store import ChromaVectorStore
from app.search.refresh_metadata import refresh_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    args = parser.parse_args()
    try:
        settings = Settings()
        store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
        updated = refresh_metadata(store, args.discovery_id)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Metadata refresh failed: {error}\n")
    print(f"Updated metadata for {updated} chunks; discovery ID: {args.discovery_id}")
    print("Chunk IDs, stored text and embeddings are unchanged.")


if __name__ == "__main__":
    main()
