# Live demo

Follow the root README to configure `.env`, then start:

```bash
docker compose up --build
```

Open http://localhost:8000 and use **How to use** for the website instructions.

## Suggested 5–10 minute walkthrough

1. Upload a bid folder and show processing. An existing indexed folder can be reopened with its discovery ID.
2. Search for a deadline or product specification and open the supporting evidence.
3. Ask a focused question and show the answer's file/page citations.
4. Select both indexed bids for a comparison question if model budget allows.
5. Demonstrate Extract, saved progress and resume. If quotas prevent completing it live, show a clearly labelled saved run.
6. Open the submission JSON files, retrieval evaluation and architecture diagrams.

Full extraction can exceed the demo length because of Groq quotas. Use your own
key, keep `.env` private and check the provider budget before the session.
Fresh installations must index their own folders; saved developer discovery IDs
are not portable. Arrange the live session with the reviewer.
