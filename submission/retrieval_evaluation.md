# Retrieval evaluation report

The evaluation uses 19 scored questions covering Bid1 and Bid2, with annotated
expected source passages. The question set and references are in
[retrieval_questions.json](retrieval_questions.json).

## Configurations and results

All three configurations were evaluated on the same question set with five
returned chunks per question.

| Configuration | Questions | Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Vector search | 19 | 0.8947 | 0.6886 |
| Hybrid search (vector + BM25 + RRF) | 19 | 0.8026 | 0.7544 |
| Hybrid search + cross-encoder reranking | 19 | 0.8421 | 0.7061 |

## Method

Recall@5 measures the fraction of expected evidence units recovered in the first
five results, averaged across questions. MRR@5 measures the reciprocal rank of
the first relevant result, averaged across questions; no relevant result scores
zero. Matching uses bid, filename, physical page and annotated content anchors.
This evaluates retrieval rather than generated answers.

Vector search recovered the most expected evidence. Hybrid search placed the
first relevant result highest on average. Reranking improved recall over hybrid
search but did not outperform vector search on this question set.

Detailed per-question results and retrieved passages are in
[retrieval_results.json](retrieval_results.json).
