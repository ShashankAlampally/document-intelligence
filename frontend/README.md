# RFP Intelligence frontend

React, TypeScript, Vite, Tailwind CSS, and Lucide icons. No persistent chat storage.

## Local development

Use Node.js 22 or newer:

```bash
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite. Start FastAPI separately on port 8000 when connecting APIs. Vite proxies `/api` and `/health` to that server. `npm run build` type-checks and produces `dist/`, which FastAPI serves when present. The root Dockerfile builds this frontend automatically; see `DOCKER.md` for single-command setup and current verification limits.

## Implemented flow

- Create and switch between chats kept in React memory.
- Queue up to 20 folders in one chat using repeated folder selections. Recursively retain PDF/HTML/HTM files, show ignored-file notices, and review names and sizes.
- Remove unprocessed folders before processing. Upload folders sequentially; retain completed discovery IDs and resume unfinished jobs after a temporary failure.
- Submit files using their relative paths, poll processing status, and unlock Ask/Search only after an actual successful indexing response.
- Send all discovery IDs belonging to that chat with every Ask/Search request. Queries unlock only when all queued folders are ready. Each question records the folder names.
- Display questions, API answers, citations, document lists, and a shared evidence drawer.
- Retain backend processing details per folder and show parsing notices in both the queue and ready workspace.
- Extract the 20 fields from one selected folder through Ask; ordinary Ask/Search still include all folders. Extraction results appear as field lines and citations.
- Handle endpoint failures without fabricating answers or indexing success.

Refresh clears frontend state. Questions are independent; message history is not sent as conversation context. Folder selection requires browser directory-input support; desktop Chrome/Edge are recommended for the demo. Backend cleanup and upload limits must be implemented by the API.

## API contract (connected)

The backend exposes `/health` and the following typed routes. They are connected to the core service adapter. All frontend integration lives in `src/lib/api.ts`:

- `POST /api/sessions`: multipart `files`, with folder-relative filenames. Returns `{id, status, discovery_id?, session_id?, detail?}`; `id` identifies the processing job.
- `GET /api/jobs/{id}`: returns the same job shape. Status is `processing`, `ready`, or `failed`; a ready response includes `discovery_id`; `session_id` remains a matching legacy alias.
- `POST /api/sessions/ask` and `/api/sessions/search`: JSON `{question, discovery_ids: ["upload-id", "another-upload-id"]}`. Returns `{answer, sources: [{file, folder_name?, discovery_id?, page?, section?, text}]}`. For search, `answer` is a short results description and `sources` contains matching passages.

The service boundary and integration responsibilities are documented in `app/api/README.md`. Failed requests leave files available for retry. Polling stops after ten minutes. IDs must be scoped and authorized by the backend; frontend state is not an isolation mechanism.

## Deferred

Dedicated structured extraction table/JSON download, container smoke testing, and conversational follow-up support. No sample answers are presented as real document results.

## Frontend checks

Run `npm run build` and `node --test tests/*.test.mjs`. Tests cover serial uploads, retry handling, required discovery IDs, and API payloads without calling a real backend.

## Result presentation

Answers support basic text formatting and simple comparison tables. Sources are numbered cards with file, folder and page/section badges. Search shows passages immediately; the evidence drawer supports source navigation, copying and original local PDF access where unambiguous. Document groups are collapsible and filterable. See `PRESENTATION_HANDOFF.md` for structured extraction, claim-to-source mapping and highlight requirements.
