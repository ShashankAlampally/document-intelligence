# Submission artifacts

Each bid JSON contains the 20 required fields with values, source citations,
confidence and notes. Submission review corrected one field per bid; those fields
have explanatory notes and no generated model confidence.

- [Bid1 JSON](bid1.json): Student and Staff Computing Devices.
- [Bid2 JSON](bid2.json): Dell Laptops with Extended Warranty.
- [Cited QA log](qa_examples.json): 18 questions with actual saved pipeline
  answers and supporting source passages.
- [Extraction trace](extraction_trace.json): full saved Bid1 extraction plus
  validation recovery, including input, searches, output, tokens and latency.
  Initial extraction and resumed validation steps are recorded once, with the
  original validation failure preserved.
- [Architecture](architecture.md).
- [Retrieval evaluation](retrieval_evaluation.md), [question set](retrieval_questions.json)
  and [detailed results](retrieval_results.json).
- [Demo guide](../DEMO.md): live demo planned instead of a recorded video; arrange
  the session with the reviewer.

Source paths containing the developer's home directory are replaced with portable
placeholders; evidence filenames, pages and text are preserved. Historical local
upload/chunk IDs identify saved runs only and cannot be loaded into a fresh database.
Confidence is an uncalibrated model estimate. Structured addendum change-log output
remains unimplemented and is explicitly recorded as a limitation.
