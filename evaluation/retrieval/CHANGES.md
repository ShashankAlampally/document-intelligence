# Source-review corrections

The current set contains 20 questions total: 19 scored retrieval questions and one manual bid-bond check. IDs remain stable for traceability. The original 25-question run is preserved in baseline-v1/.

- Correct R13 to distinguish Mercury and warranty affidavit requirements from the supplied Contract Affidavit and missing Proposal Affidavit.
- Add required deployment clarifications, a laptop-specific anchor and stronger Dell warranty anchors.
- Accept equivalent source passages as alternatives for the same evidence unit. Supporting context is documented but is not an extra scoring obligation.
- Separate laptop/dock quantity evidence; record memory and SSD SKUs as answer context.
- Retain the manufacturer/reseller question; remove the additional coverage and missing-field questions to keep the set small.
- Match by bid, normalized filename, physical PDF page and content anchors. Full source excerpts are review material and never used for grading.

No production retrieval or extraction behavior was changed. Differences from the original scores reflect changed questions and judgments, not proven search-engine improvements. Manual bond handling still requires separate answer verification.

## Reversible retrieval experiments

- Correct table evidence scoring by decoding table JSON cells and typed table-fragment escapes; gold references and question set remain unchanged.
- Add candidate-depth CLI experiments at 20/40/60 while retaining k=5.
- Add optional structure-aware indexing (default off), numbered addendum question/answer grouping, and readable table cells with original row metadata retained.
- Correct the shared splitter termination condition for trailing whitespace so short grouped sections are not repeated.
- Preserve original scoring and indexes. Compare new indexes built from the same saved source content; reuse unchanged embeddings and encode only changed passages.

These experiments measure retrieval only. The earlier statement that no production code was changed applies to the source-review revision above; this later experiment adds opt-in indexing behavior and the splitter correction. Existing candidate/grouping defaults remain unchanged.
