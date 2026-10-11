# Reproduce retrieval evaluation

1. Start the website and index Bid1 and Bid2. Copy their discovery IDs.
2. In the same environment/database, run:

```bash
python -m scripts.evaluate_retrieval --bid1 BID1_ID --bid2 BID2_ID
```

For Docker, use:

```bash
docker compose exec app python -m scripts.evaluate_retrieval --bid1 BID1_ID --bid2 BID2_ID
```

The evaluator uses `questions.json`, compares vector, hybrid and hybrid with
reranking at k=5, and saves detailed results. It uses local models without Groq.
Results and question references are also provided in `submission/`.

```bash
python -m scripts.evaluate_retrieval --prepare-only
python -m pytest tests/test_retrieval_evaluation.py -q
```

Earlier benchmark/experiment files are historical results; optional experiment
launchers were removed from the submission codebase.
