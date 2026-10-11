"""Ask one question about an indexed upload and save a local execution trace."""

import argparse
import json
from uuid import UUID, uuid4

from app.agents.qa.graph.workflow import answer_question
from app.config import Settings
from app.search.chroma_store import ChromaVectorStore
from app.search.local_embeddings import LocalEmbeddingProvider
from app.shared.groq_client import GroqModel
from app.tools.document_search import SearchTool


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    parser.add_argument("question")
    parser.add_argument(
        "--also", type=UUID, action="append", default=[], help="Additional upload ID (repeatable)"
    )
    args = parser.parse_args()
    discovery_ids = list(dict.fromkeys([args.discovery_id, *args.also]))
    try:
        settings = Settings()
        model = GroqModel(settings)
        store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
        tool = SearchTool(LocalEmbeddingProvider(settings), store, discovery_ids)
        available_tools = {"search_documents": tool}
        result = answer_question(args.question, model, available_tools)
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        trace_path = settings.log_dir / f"qa-{uuid4()}.json"
        trace_path.write_text(
            json.dumps(
                {
                    "discovery_id": str(args.discovery_id) if len(discovery_ids) == 1 else None,
                    "discovery_ids": [str(value) for value in discovery_ids],
                    "model": settings.llm_model,
                    **result.model_dump(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception as error:
        parser.exit(1, f"Setup/run failed ({type(error).__name__}). Check configuration.\n")
    print(f"Status: {result.status}\n{result.answer}")
    for source in result.sources:
        location = f"page {source['page_number']}" if source["page_number"] else source["section"]
        print(
            f"Source: {source.get('folder_name')} [{source.get('discovery_id')}]; "
            f"{source['file_name']}; {location}; chunk {source['chunk_id']}"
        )
    print(f"Trace: {trace_path}")
    if result.error:
        parser.exit(1, f"{result.error}\n")


if __name__ == "__main__":
    main()
