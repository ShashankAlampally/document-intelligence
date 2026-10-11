"""Build the frontend and serve the existing workspace without indexing or LLM calls."""

import argparse
import shutil
import subprocess

from app.config import PROJECT_ROOT, Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Check setup without starting")
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing UI build")
    args = parser.parse_args()
    settings = Settings()
    frontend = PROJECT_ROOT / "frontend"
    npm = shutil.which("npm")
    if not args.skip_build and not npm:
        parser.error("Install Node.js/npm, or use --skip-build with a prepared UI build")
    if not args.skip_build and not (frontend / "node_modules").is_dir():
        parser.error("Run npm ci in frontend first")
    if args.skip_build and not (settings.frontend_dist_dir / "index.html").is_file():
        parser.error("No frontend build found; run without --skip-build")
    print(f"Embedding: {settings.embedding_model}; dimensions: {settings.embedding_dimensions}")
    print(f"Collection: {settings.vector_collection}; database: {settings.vector_db_dir}")
    key_configured = bool(settings.groq_api_key.get_secret_value())
    print(f"LLM: {settings.llm_model}; key configured: {key_configured}")
    print("This check does not verify provider quota or model-cache readiness.")
    if args.check_only:
        return
    if not args.skip_build:
        subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
    print(f"Open http://{settings.host}:{settings.port}; stop with Ctrl+C", flush=True)
    import uvicorn

    uvicorn.run("app.main:create_app", factory=True, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
