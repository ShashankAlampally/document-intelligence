"""Extract all 20 fields, or one group, from an existing indexed upload."""

import argparse
import json
from uuid import UUID, uuid4

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from app.agents.extraction.graph.workflow import extract_field_group
from app.agents.extraction.models.field_catalog import FIELD_GROUPS
from app.config import Settings
from app.search.chroma_store import ChromaVectorStore
from app.search.local_embeddings import LocalEmbeddingProvider
from app.shared.groq_client import GroqModel
from app.tools.document_search import SearchTool


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_id", type=UUID)
    parser.add_argument("--group", choices=list(FIELD_GROUPS), help="Test one small field group")
    args = parser.parse_args()
    try:
        settings = Settings()
        model = GroqModel(settings)
        store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
        tool = SearchTool(LocalEmbeddingProvider(settings), store, args.discovery_id)
        tools = {"search_documents": tool}
        if args.group:
            print(f"Extracting group: {args.group}", flush=True)
            result = extract_field_group(model, tools, FIELD_GROUPS[args.group])
        else:
            print("Extracting all 20 fields in seven groups...", flush=True)
            result = extract_bid_fields(model, tools)
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        trace_path = settings.log_dir / f"extraction-{uuid4()}.json"
        record = {
            "discovery_id": str(args.discovery_id),
            "model": settings.llm_model,
            "field_group": args.group,
            **result.model_dump(),
        }
        trace_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Status: {result.status}")
        print(f"Trace: {trace_path}")
        if result.error:
            parser.exit(1, f"{result.error}\n")
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        suffix = ""
        if args.group:
            suffix = f"-{args.group}"
        output_path = settings.output_dir / f"fields-{args.discovery_id}{suffix}.json"
        del record["trace"]
        output_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        for name, field in result.fields.items():
            print(f"{name}: {field.value}")
        print(f"Output: {output_path}")
    except Exception as error:
        parser.exit(1, f"Setup/run failed ({type(error).__name__}). Check configuration.\n")


if __name__ == "__main__":
    main()
