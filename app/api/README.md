# Connected workspace API

`app.main.create_app()` installs `ConnectedWorkspaceService` by default. These
routes now run the existing ingestion, search and LangGraph code. The interface
in `workspace_service.py` remains replaceable for tests or another deployment.

| Route | Request | Success |
| --- | --- | --- |
| `POST /api/sessions` | multipart `files`, folder-relative filenames | 202 processing job |
| `GET /api/jobs/{job_id}` | UUID job ID | 200 processing job |
| `POST /api/sessions/ask` | SelectedDocumentQuery JSON | 200 DocumentReply |
| `POST /api/sessions/search` | SelectedDocumentQuery JSON | 200 DocumentReply |
| `POST /api/sessions/{session_id}/ask` | DocumentQuery JSON | 200 DocumentReply |
| `POST /api/sessions/{session_id}/search` | DocumentQuery JSON | 200 DocumentReply |

`ProcessingJob`: `{id, status: processing|ready|failed, discovery_id?, session_id?, detail?}`.
The job ID identifies processing; discovery_id identifies the indexed upload.
The ready response exposes both discovery_id and its matching legacy session_id
alias. Uploading the same folder again creates another job and another discovery ID.

`DocumentQuery`: `{question, top_k?: 5, file_name?, doc_type?, addendum_number?}`.
`SelectedDocumentQuery` also requires discovery_ids (1–20 UUIDs; duplicates removed).
Questions are trimmed, contain 1–4000 characters, and top_k is 1–20 **per upload**.
Doc types are bid_page, rfp, addendum, specs, or affidavit. Filters apply to both
Ask and Search. Search retrieves passages without calling Groq; Ask uses the main
graph to choose Q&A, extraction or a conversational reply.

`DocumentReply`: `{answer, sources: [{file, text, discovery_id?, folder_name?, page?, section?, chunk_id?, similarity?}]}`.
Similarity describes retrieval, not answer confidence. Evidence drawer citations
include the original folder name and source page/section. Each request is
independent; previous conversation messages are not supplied as model context.

## Execution and files

1. `folder_upload_routes.py` validates filenames and delegates to the service.
2. `workspace/files.py` saves streams before the route closes them.
3. `workspace/service.py` schedules processing and keeps CPU/network calls off
   the event loop using a worker thread. One lock serializes core operations.
4. `workspace/runtime.py` calls index_folder, caches the embedding provider/store,
   and creates a Groq client only when Ask requires it.
   The embedding service counts actual BGE tokens and splits oversized chunks
   before encoding; parsing notices do not themselves fail indexing.
5. `workspace/jobs.py` atomically persists job status for polling/restart lookup.
6. `workspace/queries.py` calls SearchTool or run_request, saves agent traces,
   and translates results using `workspace/sources.py`.

Uploaded originals: `storage/uploads/JOB_ID/FOLDER_NAME/...`.
Job records: `storage/jobs/JOB_ID.json`.
Vectors/chunks: configured vector_db_dir, normally `storage/chroma`.
Index reports: `vector_db_dir/../manifests/DISCOVERY_ID.json` (shared with CLI).
Agent traces: `logs/api-RUN_ID.json`.
Successful extraction: `outputs/fields-DISCOVERY_ID.json`.
All generated folders remain ignored by Git. Extraction requested through Ask
returns readable field lines and citations; a dedicated field editor/download UI
is still deferred. Multi-folder extraction asks for a single-folder selection.

Existing CLI-indexed uploads can be queried if their manifest and Chroma records
are present. Ready jobs persist across restarts. An unfinished job discovered
after restart becomes failed and requires a fresh upload. Failed processing keeps
saved originals for inspection; failed size-limit uploads are removed.

## Errors and operating limits

- 404: unknown job or indexed discovery ID.
- 413: upload file count/size exceeds configured limits.
- 422: invalid request, unsafe filenames or mixed folder roots.
- 429: Groq rate limit; 504: model timeout; 502: other agent failure.
- 503: missing key/dependency/configuration or other core service failure.

Set RFP_GROQ_API_KEY for Ask. Upload/index/Search do not need a Groq key. Local
embeddings download on first use unless cached; Docker preloads that cache.
Defaults: 200 files, 50 MiB per file, 200 MiB per folder. Set
RFP_UPLOAD_MAX_FILES / RFP_UPLOAD_MAX_FILE_BYTES / RFP_UPLOAD_MAX_BYTES to change
these. Saved-content limits are checked while consuming the upload; multipart
parsing may have already spooled data before this handler runs.

Run a single server process/worker with persistent storage. This local assignment
adapter uses in-process tasks, not a distributed queue. It has no account/session
authorization and is intended for the local demo. Parsing notices are reported
in job detail; no usable text means failed processing. Image-only extraction/OCR
remains deferred.

## Verification

```bash
python -m pytest tests/test_connected_workspace.py tests/test_workspace_failures.py -q
```

These tests use real parsing, preparation, chunking, Chroma and nested LangGraph
execution, with tiny deterministic embeddings and scripted LLM responses. They
cover HTML/PDF uploads, repeated folders, two-upload citations, filters, model
failures, limits, extraction output, missing keys and restart persistence without
Groq calls or model downloads.
