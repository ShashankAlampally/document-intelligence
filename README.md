# Document Intelligence

Search PDF and HTML bid documents, ask questions with citations, and extract
20 structured bid fields. The React website and FastAPI backend run together
through Docker.

## Run with Docker

1. Clone the repository and enter its folder:

   ```bash
   git clone https://github.com/ShashankAlampally/document-intelligence.git
   cd document-intelligence
   ```

2. Create `.env` **before running Docker**:

   ```bash
   cp .env.example .env
   ```

   On Windows PowerShell, use `Copy-Item .env.example .env`.

3. Open `.env` and set `RFP_GROQ_API_KEY` to your own
   [Groq API key](https://console.groq.com/keys). Keep the other defaults for the
   initial setup. Do not commit your key.
4. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
5. With `.env` configured, build and start the application:

   ```bash
   docker compose up --build
   ```

6. Open [the website](http://localhost:8000). Select **How to use** at the top for
   upload, Search, Ask and Extract instructions. API documentation is available
   at [localhost:8000/docs](http://localhost:8000/docs).

The first build downloads dependencies and local models, so allow time and
several GB of disk space. Python and Node do not need to be installed separately.
Search and indexing run locally; Ask and Extract require internet and send
selected evidence to Groq. A fresh installation must index its own folders;
example discovery IDs do not open the submitted JSON files.

## Stop, restart and view logs

```bash
docker compose down           # Stop the application; retain saved data
docker compose up -d          # Start it again in the background
docker compose logs -f app    # Follow backend logs
```

Uploads, indexes and extraction jobs persist in Docker volumes. After changing
`.env`, run `docker compose up -d --force-recreate`. Avoid `docker compose down -v`
unless you intend to delete saved data. See [DOCKER.md](DOCKER.md) for more details.

## Design

| Part | Implementation |
|---|---|
| Parsing | PyMuPDF for PDF text/tables; BeautifulSoup for HTML |
| Chunking | 1,000 characters with 100-character overlap; source metadata retained |
| Embeddings | Local BAAI/bge-large-en-v1.5; 1,024 dimensions for chunks and questions |
| Retrieval | Chroma vector search + BM25, combined using weighted RRF |
| Reranking | Optional local cross-encoder/ms-marco-MiniLM-L6-v2 |
| Agents | LangGraph planner, QA, extraction and validator workflows |
| LLM | Groq openai/gpt-oss-120b; configurable through `.env` |

Small overlapping chunks bound input size. Hybrid search combines semantic and
keyword matches. LangGraph makes routing and bounded correction loops explicit.
Prompts require evidence-based answers, valid citation IDs, applicable addendum
precedence and null values with reasons when evidence is missing. Extraction uses
seven field groups followed by validation and at most one correction pass. QA
can request one additional search round. The website's Extract action saves
progress and supports resuming paused runs.

## Submission

All example deliverables are linked in [submission/README.md](submission/README.md):

- Bid1 and Bid2 JSON outputs
- Retrieval question set and evaluation results
- Cited Q&A log and extraction trace
- Architecture diagrams showing the system and agent workflows

The submission JSON notes identify the two source-reviewed field corrections.
A live demo is planned; see [DEMO.md](DEMO.md).

## Usage limits and things to know

These notes match the website's **How to use** guide:

- **Documents:** PDF, HTML and HTM only.
- **Upload limits:** 200 files per folder, 50 MB per file and 200 MB per folder.
  A workspace supports up to 20 folders; folders are processed sequentially.
- **Indexing:** local 1,024-dimensional embeddings can take several minutes for
  larger folders, depending on your computer. Check processing warnings.
- **Groq:** Ask and Extract require an API key and internet access. Selected
  document passages are sent to Groq; folder processing and Search do not need a key.
- **Extraction time:** allow approximately 7–9 minutes on the free tier; larger
  documents, configured pacing or rate limits can make it take longer. Free-tier
  limits can cause waits or failures after retries. A partial draft is not final.
- **Questions are independent:** previous messages are not used as context.
  Include the necessary details in each question.
- **Refresh clears chats:** messages and workspace selections are kept in browser
  memory. Opened/processed bid IDs and names are remembered on this browser;
  reopen them through **Open an existing bid**. The backend index must still exist.
- **Local demo:** no user accounts or access controls; use it on your own computer.

## Tests

For a local development environment with the project dependencies installed:

```bash
python -m pytest -q
python -m ruff check app scripts tests
node --test frontend/tests/*.test.mjs
```

The final offline audit passed 428 Python tests, 16 frontend tests, Ruff and the
TypeScript/production frontend build. Dependencies are defined in
[pyproject.toml](pyproject.toml) and [frontend/package.json](frontend/package.json).
