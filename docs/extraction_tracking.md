# Extraction tracking

The website's Extract action saves its job under
`storage/extraction-jobs/<job-id>/`.

- `job.json`: status and completed draft fields.
- Successful operation files: reusable model/search responses for resume.
- `trace.json`: extraction and validation steps.
- `result.json`: completed workflow output.

The browser polls progress and remembers the job ID. After a failure, reopen the
same indexed bid and use Resume extraction. Successful identical operations are
replayed locally; remaining operations still require provider budget.

The submitted example trace is in `submission/extraction_trace.json`.
