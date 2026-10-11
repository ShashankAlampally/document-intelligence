# Retrieval experiments

All experiments use the same 19 scored questions, decoded-table scoring and k=5. The manual bond check is excluded. No LLM calls are made.

| Index | Candidates | Search | Recall@5 | MRR@5 | Median seconds/question |
|---|---:|---|---:|---:|---:|
| existing | 20 | vector | 0.8947 | 0.6886 | 0.493 |
| existing | 20 | hybrid | 0.8026 | 0.7544 | 0.432 |
| existing | 20 | hybrid_rerank | 0.8421 | 0.7061 | 3.683 |
| existing | 40 | hybrid_rerank | 0.8421 | 0.7061 | 5.476 |
| existing | 60 | hybrid_rerank | 0.8421 | 0.7061 | 5.563 |
| grouped | 20 | vector | 0.7500 | 0.6070 | 0.165 |
| grouped | 20 | hybrid | 0.7763 | 0.6421 | 0.208 |
| grouped | 20 | hybrid_rerank | 0.7895 | 0.6535 | 0.835 |
| grouped | 40 | hybrid_rerank | 0.7895 | 0.6491 | 3.217 |
| grouped | 60 | hybrid_rerank | 0.7895 | 0.6491 | 5.684 |

## Interpretation

The candidate setting applies to hybrid/reranking pools; direct vector-only search retrieves five results without a reranking pool. Compare candidate counts within one index to isolate reranking-depth changes. Compare existing versus grouped at the same count to assess grouping. Grouping uses the same 1000-character limit and 100-character overlap, regroups the fixed saved corpus at numbered addendum question/answer boundaries, and renders table cells with headers as readable text while retaining existing row metadata. Unchanged vectors are reused. Current parser changes are excluded from this controlled comparison.

Timing is diagnostic and includes local cache/runtime effects; this is not a controlled latency benchmark. Scores on this small development set do not prove improved Q&A/extraction accuracy or unseen-bid generalization.

original-scoring/ preserves the previous results. Compare them only with existing-20 to identify scoring corrections; that is not retrieval improvement.

## Recommendation

Best evidence coverage: existing / vector (Recall@5 0.8947). Recommended original-index reranking depth: 20. Keep the scoring correction independently of retrieval experiments. Grouping remains opt-in; enable it only if its measured coverage meets the project owner's acceptance criteria.
