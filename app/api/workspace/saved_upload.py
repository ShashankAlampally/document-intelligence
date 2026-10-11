"""Load an existing upload without parsing, embedding or making model calls."""

from uuid import UUID

from fastapi import HTTPException

from app.config import Settings
from app.schemas.search import IndexReport
from app.search.chroma_store import ChromaVectorStore
from app.search.store_metadata import check_model


def load_saved_upload(settings: Settings, discovery_id: UUID) -> IndexReport:
    path = settings.vector_db_dir.parent / "manifests" / f"{discovery_id}.json"
    if not path.is_file():
        raise HTTPException(
            404, "Discovery ID not found. Use the ID from a completed indexing run."
        )
    report = IndexReport.model_validate_json(path.read_text(encoding="utf-8"))
    if report.discovery_id != discovery_id or report.stored_chunks < 1:
        raise HTTPException(409, "This folder has not finished indexing.")
    try:
        store = ChromaVectorStore(settings.vector_db_dir, settings.vector_collection)
        check_model(store.info, report.model)
        found = store.collection.get(where={"discovery_id": str(discovery_id)}, limit=1, include=[])
    except ValueError as error:
        raise HTTPException(
            409, "This ID has no compatible index in the current database. Index the folder again."
        ) from error
    if not found["ids"]:
        raise HTTPException(409, "Vectors for this ID were removed. Index the folder again.")
    return report
