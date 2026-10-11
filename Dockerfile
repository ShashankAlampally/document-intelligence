# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS application
ARG TARGETARCH
ARG EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
ARG EMBEDDING_REVISION=d4aa6901d3a41ba39fb536a557fa166f842b0e09
ARG RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L6-v2
ARG RERANKER_REVISION=233902d25c440f23af6f7d6e94d2946bac0bee0a
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    RFP_EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    RFP_EMBEDDING_REVISION=${EMBEDDING_REVISION} \
    RFP_EMBEDDING_CACHE_DIR=/opt/embedding-models \
    RFP_EMBEDDING_DEVICE=cpu \
    RFP_RERANKER_MODEL=${RERANKER_MODEL} \
    RFP_RERANKER_REVISION=${RERANKER_REVISION} \
    RFP_RERANKER_CACHE_DIR=/opt/embedding-models \
    RFP_FRONTEND_DIST_DIR=/app/frontend/dist \
    RFP_HOST=0.0.0.0 \
    RFP_PORT=8000
WORKDIR /app
# Avoid the large CUDA dependencies on Linux x86; ARM uses its native PyPI wheel.
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      pip install 'torch==2.8.0' --index-url https://download.pytorch.org/whl/cpu; \
    else pip install 'torch==2.8.0'; fi
COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY scripts/ ./scripts/
RUN pip install '.[embeddings,storage,agents]'
RUN python scripts/docker/prefetch_embedding_model.py
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
COPY --from=frontend-build /frontend/dist/ ./frontend/dist/
COPY ["Assignment-Data-Statements (AI Engineer-Emplay Inc)/", "/app/Assignment-Data-Statements (AI Engineer-Emplay Inc)/"]
RUN groupadd --gid 10001 rfp && useradd --uid 10001 --gid rfp --create-home rfp \
    && mkdir -p /app/storage /app/outputs /app/logs \
    && chown -R rfp:rfp /app/storage /app/outputs /app/logs
USER rfp
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
