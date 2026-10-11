# Conditional QA search

QA first retrieves up to five passages using the user's question. One model call
then returns either a cited answer or a request for focused searches. An immediate
answer ends the graph. A search request runs at most six additional queries, combines
the evidence and makes one final answer call. There is no third round or retry loop.
The website's existing routing call is separate from these one or two QA calls.

## Execution order

1. `app/agents/qa/graph/workflow.py` creates the state and connects conditional edges.
2. `nodes/retrieve_qa_evidence.py` calls shared retrieval, adds recovered headings,
   strips ranking diagnostics from model evidence and deduplicates passage content.
3. `nodes/answer_or_search.py` asks the model to record evidence coverage for every
   material requested part, then answer or identify gaps and focused queries.
   `models/search_decision.py` overrides an immediate answer when reported gaps or
   missing coverage parts require search. It constructs question-scoped fallback
   queries without another planning call. Unknown categories must be discovered
   through list/scope queries.
4. The graph ends for an immediate answer; otherwise the same retrieval node runs with
   `additional=True`. Initial evidence and new query results compete within the budget.
   The selector takes one result from each group before lower-ranked results, retaining
   whole chunks. Initial evidence can be omitted if the combined budget is exhausted;
   previous IDs and selection decisions remain visible in traces.
5. `nodes/generate_answer.py` writes the final cited answer, reports remaining gaps and
   cannot ask for further searches.
6. `models/response_checks.py` restricts citation choices to supplied IDs and validates
   answers. `models/answers.py` defines the answer/search contract; `graph/state.py`
   carries the decision, missing information and settings between nodes.

`prompts/instructions.py` covers partial answers, official vendor-question responses,
category boundaries, numbered sections and explicit addendum changes. Instructions
cannot guarantee accurate interpretation or complete retrieval.

## Configuration

`RFP_QA_SEARCH_TOP_K=5` sets results per query; `RFP_QA_MAX_FOLLOWUP_QUERIES=6`
limits the additional plan. Both have validated defaults in `app/config.py`.
The combined evidence budget remains 15 chunks and 12,000 serialized characters.
Search uses the existing configured hybrid and reranker settings, not a new model.

Trace records include search inputs/results, initial/additional round, final selection,
answer-or-search decision, missing information, model usage and error details.
For retrieved addendum text containing a question, `search/qa_context.py` can add
one following text passage from the same source and adjacent location. It does not
assume that the passage is an official answer; the model must verify that relationship.
These supporting passages use the existing evidence budget, retain their own citation
IDs and appear in traces. No full tables are expanded. Heading context is scoped to
the upload and document and describes the start of the passage, not every bullet.
No follow-up conversation memory is introduced.

The extraction workflow is unchanged. No database migration or reindexing is required.
## Evaluation JSON tracking

`scripts/evaluate_qa.py` runs document questions through this graph. The independent
`scripts/qa_behavior.py` wrapper counts actual model invocations, including failed calls.
Every result includes a `behavior` object with the decision, missing information,
planned queries, search rounds, candidate/selected chunk IDs, selection/omission reasons,
model responses, token usage, timings and errors. Full prompts and passages remain
in the workflow trace. `run_summary` totals one-call/two-call questions and token usage.

Counts exclude the website planner and internal Groq HTTP retries. An additional search
can use only one model call if it returns no usable evidence and final generation is
skipped; `additional_search_used` makes that distinction visible. Model-call durations
include budget waits, so they are not pure inference time. Raw per-call responses allow
investigating invalid JSON or citation errors even when answer validation fails.

Tracking includes coverage, the original model decision, whether gaps forced search,
and supporting passage IDs. Resume accepts only runs marked `coverage_qa_v2`; the old
accuracy baseline is kept
separate. No reference answers are provided to QA or used as grading prompts.
Offline tests exercise real graph branches with fake models and tools, including the API.
