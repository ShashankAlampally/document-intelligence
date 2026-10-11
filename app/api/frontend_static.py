"""Serve the production frontend after API routes, when a build is available."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_frontend(application: FastAPI, directory: Path) -> None:
    if (directory / "index.html").is_file():
        # Mount last so /api, /health, /docs and OpenAPI retain their own routing.
        application.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
