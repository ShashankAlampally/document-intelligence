# Extraction Validator Agent: combined validation

Full extraction produces all seven groups first, then validates the combined
20-field draft. QA's existing answer/coverage/search flow stays unchanged.
No new packages or Chroma reindexing are required.

## Execution order

1. `graph/extract_bid.py` runs the seven groups sequentially through
   `graph/workflow.py`. Each group retrieves evidence and calls the extraction
   model once, without a validation call after that group.
2. Drafts, evidence and traces are combined. `graph/validation_workflow.py`
   starts the final validation/correction graph.
3. `models/validation_batches.py` packs complete fields and their cited passages
   into as few bounded batches as possible. Shared passages appear once per batch.
   Uncited retrieval candidates are not sent to the validator.
4. `nodes/validate_fields.py` reviews the batches using
   `nodes/review_validation_batch.py`, `prompts/validation.py` and
   `models/validation.py`.
5. If fields are rejected, `nodes/correct_fields.py` routes them into their original
   small groups. `nodes/correct_field_batch.py` searches only fields marked
   `needs_evidence`, then re-extracts only rejected fields with validator feedback.
   `incorrect` fields use their existing cited evidence. Accepted fields are retained.
6. The combined validator checks only corrected fields once more. Persistent
   rejections return null, confidence 0, and an unresolved reason. No third attempt.
7. `models/build_result.py` resolves citations and includes the final decisions for
   every field in `validation_report`.

All paths above are under `app/agents/extraction/`. The single-group CLI still
validates the requested group. The website, full extraction CLI and full tracking
script use combined validation. Tracking saves unvalidated drafts after each group
with status `running`; only successful final validation produces `completed`.

## Decisions and limits

- `accepted`: cited evidence supports the value and scope, including a clearly
  explained unresolved conflict where applicable.
- `needs_evidence`: missing or materially incomplete evidence, including an uncited null.
- `incorrect`: existing evidence can correct an interpretation or unsupported claim.

These are model judgments, not guaranteed correctness. A validator using the same
model can still overlook errors, especially when the necessary passage was never
cited. It checks the supplied evidence, not every page of the original documents.
Offline tests verify routing and contracts; live accuracy requires authorization
and manual source review.

## Model calls and Groq

When cited evidence fits one validation batch and no fields are rejected, full
extraction uses **7 extraction calls + 1 validation call = 8**. The website adds
one planner call. Eight is conditional, not a guarantee.

For larger evidence: total calls = initial extraction calls + initial validation
batches + correction-group calls + corrected-field validation batches. A small
input with every group rejected uses 7 + 1 + 7 + 1 = 16 calls. Large inputs may
need more validation batches. Provider retries are additional HTTP attempts.

Before separating the evidence and payload limits, a sizing-only check on an
earlier saved Bid1 20-field result required six batches: 7 + 6 = 13 calls before any corrections (plus the website
planner). No Groq calls were made for that check. Fewer calls do not bypass the
provider's token-per-minute quota, and actual elapsed-time savings are unmeasured.

Validation evidence is capped at 12,000 characters and 15 cited chunks. The
complete payload (fields + evidence JSON) has a separate 16,000-character cap. System instructions/schema are additional; this is not an exact
token limit. Complete passages are never truncated. If a single field plus all its
citations exceeds the cap, return an explicit error rather than silently dropping
citations or skipping validation. Correction evidence uses the existing 15-chunk /
12,000-character budget; earlier evidence remains in state for final source resolution.
Empty evidence triggers one local retrieval retry without model calls.

## Reports and failures

`validation_report` contains final decisions and the correction count.
`trace` retains validation batch indexes/counts, payload size, model-called flags,
reasons, usage, timing, both validation rounds, correction inputs and searches.
The tracking report counts validation calls and displays their decisions.

Malformed responses, timeouts, oversized individual fields and tool failures are
explicit errors, not acceptance. Draft progress remains inspectable in the tracking
script. Drafts saved before validation should not be treated as verified results.

## Offline verification

From the project root:

```sh
.venv/bin/python -m pytest -q tests/test_combined_extraction_validation.py tests/test_validation_batches.py tests/test_extraction_validator.py tests/test_tracking_script.py
.venv/bin/python -m ruff check app tests scripts
```

Tests cover combined-call order, deduplicated evidence, automatic batching without
citation loss, accepted-field preservation, field-only searching/correction, retry
limits, null outcomes, provider/contract errors, budget bounds, tracking and API routing.

For a live website test, restart the backend, use an existing discovery ID and ask
for all fields. Inspect the saved fields JSON and API trace. Reindexing is unnecessary.
No live test was run for this implementation.

## Failure-tracking updates

The tracking script now saves timestamped `events.jsonl` entries before searches
and model calls. Search exceptions include their request and detailed message.
Model events include a call ID, schema name, response format, inputs, raw outputs,
status codes and detailed exceptions. API keys and authorization headers are not
recorded by these tracking hooks.

During a tracked call, an optional observer on the existing Groq limiter records
HTTP attempt start/end, provider errors, scheduled retries, wait start/end, actual
observed wait duration, and retry/wait-limit termination. It does not change pacing
or retry settings, and the observer is restored after success, error or Ctrl-C.
`groq_diagnostics` and `report.md` summarize current-run HTTP attempts, retries,
waits and provider error statuses. Resumed historical trace entries are separate
from the new directory's event totals.

Completed validation batches and correction groups are saved into `trace.json`
as they finish, before the next call. Ctrl-C preserves these completed steps and
marks the run interrupted. Raw events retain the input for the interrupted call.
An abrupt process kill can leave an unfinished last event/wait; exact elapsed time
cannot be recovered for a process that never recorded its end event.

Offline tracking checks:

```sh
.venv/bin/python -m pytest -q tests/test_pipeline_tracking_events.py tests/test_groq_rate_limit.py tests/test_tracking_script.py
```

## Validate saved drafts after a failed run

Run the new command against a tracking output directory containing `trace.json`:

```sh
.venv/bin/python -m scripts.validate_saved_extraction \
  outputs/pipeline-e6830bc5-4866-4caa-a2d7-b95f8c9e5b39-20261011T054528616150Z \
  --prepare-only
```

This preflight is offline: it verifies all 20 saved fields, their exact cited
passages, upload identity, and the batch budgets. It creates no model or database.
The failed run above now fits four initial validation batches; its Bid Summary
has room for the field overhead without raising the evidence limit.

Remove `--prepare-only` to run live validation. That run uses the same validation
and correction graph as the website. It does not repeat initial extraction.
Rejected fields can still cause targeted searches and re-extraction, followed by
one more validation round. Groq pacing remains active.

Results, events and progress are written into a new `outputs/validation-...`
directory. Original saved files remain unchanged. The original trace and elapsed
time are retained as history, while `groq_diagnostics` counts only new-run events.
Missing fields, missing cited passages or inconsistent sources fail before any
model calls. This command requires the indexed upload for possible corrections.
An interruption saves completed validation/correction steps with interrupted status.
