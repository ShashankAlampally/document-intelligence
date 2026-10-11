"""Command-line entry point for the platform."""

import argparse

import uvicorn

from app.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="RFP Intelligence platform")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the FastAPI server")
    serve.add_argument("--reload", action="store_true", help="Reload on code changes")
    commands.add_parser("check-config", help="Validate configuration and show data paths")
    args = parser.parse_args()
    settings = Settings()

    if args.command == "check-config":
        print(f"Data directory: {settings.data_dir}")
        print(f"Data directory exists: {settings.data_dir.is_dir()}")
        print(f"Storage directory: {settings.storage_dir}")
        print(f"Output directory: {settings.output_dir}")
        print(f"Log directory: {settings.log_dir}")
        if not settings.data_dir.is_dir():
            parser.exit(status=1, message="Configured data directory does not exist.\n")
        return

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
