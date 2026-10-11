# Frontend

React and TypeScript website for uploading bid folders, searching passages,
asking cited questions and extracting the 20 bid fields.

## Local development

Start the backend on port 8000, then run:

```bash
npm ci
npm run dev
```

Open the URL printed by Vite. Requests to `/api` are proxied to the backend.
For the combined Docker setup, follow the [root README](../README.md).

## Features

- Process multiple folders and open saved discovery IDs.
- Ask and Search across selected folders; Extract processes one folder.
- Read source citations and supporting evidence.
- View extraction drafts and resume paused extraction jobs.
- Open **How to use** for usage limits and Groq setup instructions.

Chat messages are not persistent conversational memory. Saved bid references
remain on this browser, but the corresponding backend index must still exist.

## Build and checks

```bash
npm run build
node --test tests/*.test.mjs
```
