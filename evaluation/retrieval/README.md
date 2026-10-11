# Retrieval evaluation

The current set has **20 questions total: 19 scored retrieval questions and one manual bid-bond check**. It covers both bids and the assignment's five sample question types. The original set was source-reviewed; revised references remain pending owner review.

## What to submit

Keep this directory and the evaluation scripts in the submitted repository:

- `QUESTIONS.md`: questions, expected evidence and source notes for review.
- `questions.json`: machine-readable references with source excerpts and file hashes.
- `results.md`: comparison table, scoring method and missing-evidence cases.
- `results.json`: every returned passage, score and retrieval configuration.

No separate website is needed. Local model weights and Chroma databases are not submission artifacts. The main project README contains the results table.

## How scoring works

Recall@5 measures how much annotated evidence appears in the first five results. MRR@5 measures how near the top the first useful passage appears: first = 1, second = 0.5, missing from the first five = 0. Both are averaged across questions.

A match requires the correct bid, filename, physical PDF page and all content anchors. Filenames tolerate spaces, underscores, case and punctuation variants. Content matching tolerates case, punctuation and whitespace. Source excerpts are only for human review, not grading.

Equivalent passages sharing an `evidence_id` count as alternatives for one evidence unit. Supporting passages provide context and are not extra recall obligations. Duplicate chunks do not increase recall. PDF pages are one-based physical page indices, not printed footer labels; HTML pages are null.

The manual bond question is excluded from Recall/MRR. No explicit amount was identified, so a cautious answer should say not found rather than inventing an amount or saying not required. This evaluator does not generate or grade answers.

## Run again

Use the project virtual environment with the documented embedding, storage and agent dependencies. Index both folders if compatible complete indexes do not already exist:

```bash
python -m scripts.index_folder "Assignment-Data-Statements (AI Engineer-Emplay Inc)/Bid1"
python -m scripts.index_folder "Assignment-Data-Statements (AI Engineer-Emplay Inc)/Bid2"
```

Use the discovery IDs printed by indexing:

```bash
python -m scripts.evaluate_retrieval --bid1 BID1_DISCOVERY_ID --bid2 BID2_DISCOVERY_ID
```

To prepare the question review file or test the scoring without loading models:

```bash
python -m scripts.evaluate_retrieval --prepare-only
python -m pytest tests/test_retrieval_evaluation.py -q
```

All three configurations use the same questions and indexes. Only questions and bid IDs enter search; gold references never do. Embedding and reranking run locally without Groq calls. Uncached model weights download on first use. Each run starts fresh and checkpoints searches; errors make the run incomplete.

## Limits and earlier results

This is a small development benchmark, not an unseen-bid test or proof of extraction accuracy. Strict anchors may under-credit split or differently extracted text. Inspect saved misses before diagnosing ranking. Cross-bid results are merged by configuration score and limited to five total; the app may display separate per-bid results. Latency is diagnostic, not a controlled speed comparison.

`baseline-v1/` preserves the original 25-question run. Current scores are not directly comparable to it because questions and relevance judgments changed. No production retrieval behavior was changed by this revision. `CHANGES.md` records the corrections. Reference corrections require rerunning all configurations.

## Optional improvement experiments

The evaluator now decodes table JSON and escaped newlines in explicitly typed table fragments. This corrects false misses without weakening the bid/file/page/anchor requirements. `experiments/original-scoring/` preserves the previous measurements; an increase from this correction is not a retrieval-engine improvement.

Candidate-count experiments keep k=5 and use `--candidates 20`, `40` or `60`. Each value sets vector, keyword and reranking candidate limits. The combined experiment report is `experiments/comparison.md`.

The grouping experiment is opt-in. `python -m scripts.index_folder FOLDER --structure-aware` keeps numbered addendum question/answer boundaries and renders tables as readable cells with available headers. Native structured row data remains attached. Set `RFP_INDEX_STRUCTURE_AWARE=true` to use it for newly indexed folders in the API; the default is false. Changing it requires indexing a new folder/chat and does not change existing vectors.

For a controlled comparison using exactly the original indexed source content, create separate variant discovery IDs:

```bash
python -m scripts.index_retrieval_variant --from-id ORIGINAL_BID1_ID
python -m scripts.index_retrieval_variant --from-id ORIGINAL_BID2_ID
python -m scripts.retrieval_experiments --bid1 ORIGINAL_BID1_ID --bid2 ORIGINAL_BID2_ID --grouped-bid1 VARIANT_BID1_ID --grouped-bid2 VARIANT_BID2_ID
```

The snapshot command reconstructs addendum blocks from validated source offsets, decodes table text, reuses unchanged vectors and embeds changed passages with the same model. It does not reparse files or use evaluation answers. Snapshot variant IDs are for the CLI benchmark; normal application chats should use folder indexing with the optional flag. The original indexes remain available. The settings and runs are saved so the grouping/candidate changes can be retained or disabled independently.

To disable grouping, leave `RFP_INDEX_STRUCTURE_AWARE=false` and omit `--structure-aware`. To use the original candidate depth, keep `RFP_SEARCH_VECTOR_CANDIDATES=20`, `RFP_SEARCH_KEYWORD_CANDIDATES=20` and `RFP_SEARCH_RERANK_CANDIDATES=20`. No new model or LLM provider is added.

Measured outcome: keep the corrected scoring, original grouping and 20 candidates. Larger candidate pools did not improve original-index Recall/MRR; grouping lowered scores for all three approaches at 20 candidates. The original vector search has the best measured evidence coverage (Recall@5 0.8947), while original hybrid has the highest MRR@5 (0.7544). The candidate/grouping defaults were not changed. Relevant regression tests: 142 passed.
