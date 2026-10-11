"""Inspect local cross-encoder scores without Chroma changes or Groq calls."""

from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.schemas.chunks import Chunk
from app.schemas.metadata import SourceMetadata
from app.schemas.search import SearchHit
from app.search.cross_encoder_reranker import CrossEncoderReranker


def main():
    source = SourceMetadata(
        discovery_id=uuid4(),
        folder_name="Demonstration",
        file_name="example.pdf",
        file_type="pdf",
        relative_path=Path("example.pdf"),
        file_path=Path("/example.pdf"),
    )
    passages = [
        "Equipment must arrive within 45 days of award.",
        "Procurement contact: Jane Smith, jane@example.org, 555-1234.",
    ]
    hits = [
        SearchHit(
            chunk=Chunk(
                chunk_id=uuid4(),
                source=source,
                page_number=1,
                block_index=index,
                start_char=0,
                end_char=len(text),
                text=text,
            )
        )
        for index, text in enumerate(passages)
    ]
    query = "Who is the procurement contact?"
    print(f"Question: {query}", flush=True)
    for hit in CrossEncoderReranker(Settings()).rerank(query, hits, 2):
        print(f"Relevance score: {hit.rerank_score:.4f}\n{hit.chunk.text}\n")
    print("Demonstration passages only. No Groq calls or database changes.")


if __name__ == "__main__":
    main()
