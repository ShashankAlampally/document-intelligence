"""Inspect the agent search payload without calling Groq."""

import argparse
import json
from uuid import UUID

from app.config import Settings
from app.search.chroma_store import ChromaVectorStore
from app.search.local_embeddings import LocalEmbeddingProvider
from app.tools.document_search import SearchTool


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    parser.add_argument("query")
    parser.add_argument("--also", type=UUID, action="append", default=[])
    args = parser.parse_args()
    settings = Settings()
    store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
    tool = SearchTool(LocalEmbeddingProvider(settings), store, [args.discovery_id, *args.also])
    print(json.dumps(tool.run({"query": args.query}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
