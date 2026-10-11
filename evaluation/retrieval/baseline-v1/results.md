# Retrieval evaluation report

Status: **completed**. Question references remain draft until user review.

Dataset SHA-256: `6c66f223983d5d94fe17f0f838465c40ac05a825d5b73c6b01c0855a9efaacb9`

| Configuration | Questions | Errors | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|
| vector | 25 | 0 | 0.8000 | 0.5867 |
| hybrid | 25 | 0 | 0.7000 | 0.5800 |
| hybrid_rerank | 25 | 0 | 0.7800 | 0.6047 |

## Method

Recall is the fraction of annotated evidence units recovered, averaged per question. MRR uses the first result matching any expected unit. Overlapping chunks cannot increase a unit's recall above one. A correct file/page without the required content anchors earns no credit.

These are annotated evidence-unit metrics, not exhaustive relevance judgments over every corpus chunk. Exact normalized anchors make grading reproducible but may under-credit differently extracted or split text. Inspect saved misses before drawing conclusions; do not tune references to favor retrieved results.

All configurations use the same immutable question set, selected uploads and top-k. Cross-bid search gets k candidates per bid, merges by the configuration's score, then keeps k total. References never enter search. No LLM generation or grader is used. Latency includes local inference/cache effects and is diagnostic, not a controlled benchmark.

Errors are recorded separately and make the run incomplete; their questions are not silently scored as retrieval misses. Only complete runs should be compared.

## Questions with missing expected evidence

- vector / R02: passage ranks: [None, 1]
- vector / R03: passage ranks: [None]
- vector / R06: passage ranks: [None]
- vector / R09: passage ranks: [None]
- vector / R13: passage ranks: [1, None]
- vector / R18: passage ranks: [1, None]
- vector / R25: passage ranks: [3, None]
- hybrid / R01: passage ranks: [None]
- hybrid / R02: passage ranks: [None, 1]
- hybrid / R03: passage ranks: [None]
- hybrid / R06: passage ranks: [None]
- hybrid / R07: passage ranks: [None]
- hybrid / R09: passage ranks: [None]
- hybrid / R11: passage ranks: [None]
- hybrid / R13: passage ranks: [None, None]
- hybrid_rerank / R02: passage ranks: [None, 1]
- hybrid_rerank / R06: passage ranks: [None]
- hybrid_rerank / R09: passage ranks: [None]
- hybrid_rerank / R13: passage ranks: [2, None]
- hybrid_rerank / R17: passage ranks: [None]
- hybrid_rerank / R18: passage ranks: [1, None]
- hybrid_rerank / R22: passage ranks: [None]

## Evidence units unavailable as a single indexed chunk

- R06 / unit 1: Bid1 / JA-207652 Student and Staff Computing Devices FINAL.pdf / page 9. The complete anchor set does not coexist in a stored chunk. This limits achievable recall under the strict matching rule; review annotation granularity and chunk boundaries before diagnosing ranking.

Full configuration, source/index fingerprints, metrics and exact returned passages are in the adjacent results JSON. The manual bond/abstention check is excluded from these metrics.
