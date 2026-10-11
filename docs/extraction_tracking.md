# Extraction improvements and tracking

Use an existing discovery ID. These changes do not change stored vectors and do not require re-indexing.

## Execution order

`app/agents/extraction/graph/workflow.py` connects each group to the shared retrieval graph and passes its search plan through `app/agents/shared/state.py`. The normal application uses `app/agents/extraction/graph/extract_bid.py` to run the seven groups; the tracker calls the same group function directly so it can save results incrementally and rerun selected groups. `app/search/cross_encoder_reranker.py` uses recovered heading context when scoring focused passages, while preserving their original text and citations.

1. `scripts/track_extraction.py` loads configuration, verifies stored chunks and creates a separate output folder for this run.
2. `app/agents/extraction/models/field_catalog.py` defines seven groups containing the 20 fields.
3. `app/agents/extraction/prompts/retrieval_plan.py` creates the local searches: simple fields have one query; products have three, required documents six, specifications six, and contacts two. A full run makes 33 local searches.
4. `app/tools/document_search.py` scopes every search to the discovery ID. Focused product searches use explicit topic words to avoid substituting unrelated categories.
5. `app/search/service.py` retrieves vector and BM25 candidates, combines them using RRF, applies topic anchors when requested, and reranks the surviving candidates. Normal QA searches keep their existing behaviour.
6. `app/search/heading_context.py` recovers explicitly stated nearby specification headings from already stored text. A heading may carry over to the next page. It does not invent headings, alter chunk text, append a full table or add missing specifications.
7. `app/agents/shared/retrieve_evidence.py` seeds one search per field, then includes the extra topic searches before lower ranks, and records the search results and selection decisions.
8. `app/agents/shared/evidence_content.py` compares text/table content within the same source location. It preserves different sources and changed numeric requirements. Ranking scores are retained in the trace, but excluded from extraction input.
9. `app/agents/shared/select_evidence.py` selects whole chunks within the same 15-chunk and 12,000-character limits. It records content duplicates and budget omissions. Coverage is still bounded; these limits cannot guarantee a complete answer for an arbitrarily large document.
10. `app/agents/extraction/prompts/instructions.py` instructs the model to distinguish questions from official answers, preserve requirement scope, handle allowed alternatives, avoid assumptions and acknowledge incomplete coverage.
11. `app/agents/extraction/nodes/extract_fields.py` sends the selected evidence to Groq. The shared client still manages waits and retries. Seven groups mean seven extraction calls; the main application also makes its planner call. The tracking CLI invokes extraction directly, without a planner call.
12. `app/agents/extraction/models/check_fields.py` checks field structure and citation IDs. These checks do not prove factual correctness.
13. `scripts/pipeline_tracking.py` writes each search and the model input before calling Groq. `scripts/pipeline_report.py` writes a readable report, preserving completed groups if later groups fail.

## Commands

Inspect retrieval without making Groq calls:

```bash
python -m scripts.track_extraction DISCOVERY_ID --retrieval-only
```

Run extraction and compare it with a saved result:

```bash
python -m scripts.track_extraction DISCOVERY_ID --baseline outputs/fields-DISCOVERY_ID.json
```

Run just one group:

```bash
python -m scripts.track_extraction DISCOVERY_ID --group summary_and_specs
```

Repeat only affected groups while retaining prior results and traces:

```bash
python -m scripts.track_extraction DISCOVERY_ID --resume-from outputs/pipeline-PREVIOUS/trace.json --group bid_details
```

Repeat `--group` to select several groups. Replaced fields are removed before rerunning, so an error cannot silently leave their old answers in the new result. The original output folder is preserved.

Each run prints its output directory. It contains:

- `events.jsonl`: searches and their returned chunks, exact model inputs, responses, timing and failures, written incrementally.
- `trace.json`: group-level searches, ranking scores on returned chunks, selected evidence, omission reasons, configuration and model usage.
- `fields.json`: the extracted values and their citations.
- `report.md`: readable queries, evidence, outputs, usage and differences from the baseline.

The tracker records the ranked chunks returned to the agent, not every internal vector/BM25 candidate or individual HTTP retry. A source-based accuracy review is separate; the script does not assign itself an accuracy score.

## Offline verification

```bash
python -m pytest -q
```

Regression tests cover topic filtering, heading continuity, text/table duplicates, different numeric values, field balancing, budgets, graphs, citation contracts and tracking error reports. No Groq calls are made by these tests.
