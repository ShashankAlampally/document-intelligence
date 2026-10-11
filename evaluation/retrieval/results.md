# Retrieval evaluation report

Status: **completed**. References: source-reviewed revision; expanded references pending owner review.

Dataset SHA-256: `d3f2636a8a455c3d482bd7af08329cb524759d2688b2d9c589531fecb992c55f`

| Configuration | Questions | Errors | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|
| vector | 19 | 0 | 0.8947 | 0.6886 |
| hybrid | 19 | 0 | 0.8026 | 0.7544 |
| hybrid_rerank | 19 | 0 | 0.8421 | 0.7061 |

## Method

Recall is the fraction of annotated evidence units recovered, averaged per question. MRR uses the first result matching any expected unit. Overlapping chunks cannot increase a unit's recall above one. Alternatives sharing an evidence_id satisfy the same unit; supporting context is not required for credit. Filename matching ignores case and punctuation, while bid, physical page and content must match. Table JSON cells and explicitly typed table fragments are decoded before matching. A correct file/page without the required content anchors earns no credit.

These are annotated evidence-unit metrics, not exhaustive relevance judgments over every corpus chunk. Exact normalized anchors make grading reproducible but may under-credit differently extracted or split text. Inspect saved misses before drawing conclusions; do not tune references to favor retrieved results.

All configurations use the same immutable question set, selected uploads and top-k. Cross-bid search gets k candidates per bid, merges by the configuration's score, then keeps k total. References never enter search. No LLM generation or grader is used. Latency includes local inference/cache effects and is diagnostic, not a controlled benchmark.

Errors are recorded separately and make the run incomplete; their questions are not silently scored as retrieval misses. Only complete runs should be compared.

## Questions with missing expected evidence

- vector / R02: passage ranks: [None, 1]
- vector / R07: passage ranks: [4, None, None, 3]
- vector / R13: passage ranks: [None, 3, None, 1]
- vector / R18: passage ranks: [1, None]
- hybrid / R01: passage ranks: [None]
- hybrid / R02: passage ranks: [None, 1]
- hybrid / R07: passage ranks: [None, None, None, 3]
- hybrid / R11: passage ranks: [None]
- hybrid / R13: passage ranks: [None, 4, None, 1]
- hybrid_rerank / R02: passage ranks: [None, 1]
- hybrid_rerank / R07: passage ranks: [5, None, None, 1]
- hybrid_rerank / R13: passage ranks: [3, 4, None, None]
- hybrid_rerank / R18: passage ranks: [1, None]
- hybrid_rerank / R22: passage ranks: [None]

## Evidence units unavailable as a single indexed chunk

Every annotated evidence unit has at least one matching indexed chunk.

Full configuration, source/index fingerprints, metrics and exact returned passages are in the adjacent results JSON. All manual missing-field checks are excluded from these metrics.
