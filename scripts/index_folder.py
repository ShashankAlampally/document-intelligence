"""Index a folder with stage timings and local embedding progress; no Groq calls."""

import argparse
from pathlib import Path
from time import perf_counter

from app.api.workspace.files import save_json
from app.api.workspace.runtime import PipelineRuntime
from app.config import Settings
from app.schemas.chunks import ChunkSettings
from app.search.indexer import index_folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing PDF/HTML documents")
    parser.add_argument("--structure-aware", action="store_true")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Folder does not exist: {folder}")
    settings = Settings()
    print(
        f"Model: {settings.embedding_model}; dimensions: {settings.embedding_dimensions}; "
        f"device: {settings.embedding_device}; batch size: {settings.embedding_batch_size}",
        flush=True,
    )
    started = perf_counter()
    runtime = PipelineRuntime(settings)
    try:
        if args.structure_aware:
            report = index_folder(
                folder,
                runtime.provider,
                runtime.store,
                ChunkSettings(max_chars=1000, overlap_chars=100, structure_aware=True),
            )
            manifest = settings.vector_db_dir.parent / "manifests" / f"{report.discovery_id}.json"
            save_json(manifest, report.model_dump_json(indent=2))
        else:
            report = runtime.index(folder)
    except Exception as error:
        parser.exit(1, f"Indexing failed ({type(error).__name__}): {error}\n")
    print(f"\nIndexing completed in {perf_counter() - started:.1f}s")
    print(f"Folder: {report.folder_name}\nDiscovery ID: {report.discovery_id}")
    print(f"Stored vectors: {report.stored_chunks}; dimensions: {report.model.dimensions}")
    manifest = settings.vector_db_dir.parent / "manifests" / f"{report.discovery_id}.json"
    print(f"Report: {manifest}")


if __name__ == "__main__":
    main()
