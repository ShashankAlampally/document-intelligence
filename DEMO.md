# Demo preparation and walkthrough

## Start on the current Mac

Keep the existing `.env` and stored indexes. From the project root:

```bash
.venv/bin/python -m scripts.demo --check-only
.venv/bin/python -m scripts.demo
```

The second command builds React and serves the website and API at
http://localhost:8000 (or the configured host/port). Stop with Ctrl+C.
It does not index folders or call Groq at startup. A first search can load local
models; asking questions and extracting fields makes real Groq calls.
If dependencies are missing, follow README setup and run `npm ci` in `frontend`.
After a successful build, `--skip-build` starts without rebuilding React.
Stop another server on the same port before starting this launcher.

## Prepare before recording

- Use the website's existing-discovery-ID input to load already indexed folders:
  Bid1 `e6830bc5-4866-4caa-a2d7-b95f8c9e5b39`,
  Bid2 `1a232200-07a8-4085-9639-6dd4c196e352`.
  These IDs are specific to this local database; a fresh installation must index
  the supplied folders and use its newly generated IDs.
- Verify both IDs load and try a document search to warm local models.
- Check actual Groq limits in the dashboard. Do not raise local token pacing
  above the account's allowance. Check that no evaluation script is using quota.
- Keep the completed extraction report and retrieval evaluation available.
  Show saved output explicitly as a previous run, not as a live response.
- Record only the browser and selected source/output files; hide `.env` and keys.

## Suggested 5–10 minute walkthrough

1. Explain the goal: upload a bid, retrieve evidence, ask cited questions, extract
   20 fields. Show folder selection and processing status; explain that existing
   IDs avoid repeating indexing during the demonstration.
2. Search for a deadline or a product SKU. Open a source and show file/page citations.
3. Ask one focused question live, such as the final Bid1 submission deadline.
   Check quota before this step; waits are real provider-budget waits.
4. Select both folders and demonstrate a warranty comparison, if time/quota permit.
5. Show the completed 20-field extraction, citations, validation decisions and
   correction trace. Full live extraction can exceed the video length under
   free-tier pacing; show a labelled saved run instead of promising instant completion.
6. Show retrieval results: corrected vector Recall@5 89.47%, hybrid 80.26%,
   hybrid plus reranking 84.21%. Explain that retrieval coverage differs from
   answer accuracy and that the evaluation uses no Groq calls.
7. Explain known limitations: incomplete answers, table-category interpretation,
   no OCR, rate-limited extraction, and pending addendum change-log output.

## Reviewer reproduction

Use DOCKER.md for the container path. Local discovery IDs and databases are not
portable submission artifacts. The reviewer uses their own key and indexes their
folders. Model weights are downloaded/cached rather than committed to Git.
Docker execution still requires a real build/start check; packaging alone is not
proof that it runs. Functional accuracy work remains separate from demo setup.
