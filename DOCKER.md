# Run RFP Intelligence with Docker

## Current readiness

Docker packaging builds the React frontend and serves it with FastAPI at one URL.
The folder/query HTTP routes now connect to the ingestion, Chroma and agent
pipeline. Search is key-free; Ask needs RFP_GROQ_API_KEY.

The Docker executable is unavailable in the development environment where this
setup was written. Python static-serving tests and the frontend build were run;
an actual Docker image build/start still needs verification on Docker Desktop.

## Reviewer setup

1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
   and start it. No separate Python or Node installation is needed.
2. Clone/download this repository and open a terminal in `Emplay_Assignment`.
3. Copy `.env.example` to `.env` (skip this if you already have a configured `.env`):

   ```bash
   cp .env.example .env
   ```

   On Windows PowerShell use `Copy-Item .env.example .env`.
4. Edit `.env` and set `RFP_GROQ_API_KEY` to your own key. Never include your real
   `.env` in the repository or submission. Search/indexing use a local embedding
   model; real LLM Q&A/extraction require Groq access once integrated.
5. Run:

   ```bash
   docker compose up --build
   ```

6. Open http://localhost:8000 for the UI, http://localhost:8000/docs for API
   documentation, or http://localhost:8000/health for process health.

The first build downloads base images, Python packages, and the pinned BGE model.
This takes time and needs internet access and several GB of available disk space.
The Docker image is larger than the embedding model alone because it includes
PyTorch and the Python runtime. Use a few GB of available RAM for building and
running; actual requirements depend on document volume and must be measured.

The embedding and reranking models are baked into the image and loading is configured offline at
runtime. Groq requests still require internet access. Changed model/revision
settings require rebuilding the image. Only public embedding models are supported
by this build; do not pass private model tokens as build arguments.

## Useful commands

```bash
# Start an existing image in the background
docker compose up -d

# Watch application logs
docker compose logs -f app

# Check process health
docker compose ps

# Stop and remove the application container
docker compose down
```

If port 8000 is occupied, add `RFP_WEB_PORT=8001` to `.env` and open
http://localhost:8001. The container still listens on port 8000.

## Data and configuration

- React chats live in browser memory and clear on refresh.
- Runtime files/indexes, outputs and logs use named Docker volumes and survive
  `docker compose down`. `docker compose down -v` deletes those volumes; do not use
  it when you want to retain indexed folders. Host Mac indexes are not copied in.
- Session expiry and upload cleanup remain the responsibility of the future core
  adapter; Docker does not implement application session cleanup.
- Provided assignment folders are copied into the image for CLI demonstrations.
  Other folders are uploaded through the UI.
- `.env`, host indexes, logs, cached models and node_modules are excluded from the
  build context. The key is supplied at container startup through Compose.
- Compose forces Linux container paths and CPU embeddings so local macOS paths or
  embedding-device settings cannot break the container.
- One non-root Python process serves static assets and API requests. The port is
  bound to loopback on your laptop; this setup does not publish a hosted website.
- `/health` checks process responsiveness, not indexing/model readiness.

## Smoke test once Docker is installed

Build/start the service, confirm `/`, `/health`, `/docs` and a referenced frontend
asset respond successfully, then test the actual Bid1 and Bid2 folder → processing
→ search/ask → citation flow. Confirm each ready job includes discovery_id.
The adapter uses in-process jobs, so run one server worker. Mount/preserve storage
if uploads and vectors should survive container removal.

Useful model-cache verification after the image build:

```bash
docker compose run --rm app python scripts/docker/prefetch_embedding_model.py
```

Runtime offline settings make that command fail if the required model files were
not cached correctly. The application image supports native amd64/arm64 builds;
both architectures still need container verification before claiming portability.
