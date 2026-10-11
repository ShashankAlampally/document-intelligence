"""Send one request about an indexed upload through the main graph."""

import argparse
import json
from uuid import UUID, uuid4

from app.agents.planner.graph.workflow import run_request
from app.config import Settings
from app.search.chroma_store import ChromaVectorStore
from app.search.local_embeddings import LocalEmbeddingProvider
from app.shared.groq_client import GroqModel
from app.tools.document_search import SearchTool


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    parser.add_argument("request")
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
        result = run_request(args.request, discovery_ids, model, {"search_documents": tool})
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        trace_path = settings.log_dir / f"main-{uuid4()}.json"
        trace_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"Trace: {trace_path}")
        if result.error:
            parser.exit(1, f"{result.error}\n")
        if result.qa_result is not None:
            print(result.qa_result.answer)
            for source in result.qa_result.sources:
                print(
                    f"Source: {source.get('folder_name')} [{source.get('discovery_id')}]; "
                    f"{source['file_name']}; page={source['page_number']}; "
                    f"section={source['section']}"
                )
        if result.extraction_result is not None:
            settings.output_dir.mkdir(parents=True, exist_ok=True)
            path = settings.output_dir / f"fields-{args.discovery_id}.json"
            record = {
                "discovery_id": str(args.discovery_id),
                "discovery_ids": [str(value) for value in discovery_ids],
                "model": settings.llm_model,
                **result.extraction_result.model_dump(exclude={"trace"}),
            }
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Fields: {len(result.extraction_result.fields)}; output: {path}")
    except Exception as error:
        parser.exit(1, f"Setup/run failed ({type(error).__name__}). Check configuration.\n")


if __name__ == "__main__":
    main()
