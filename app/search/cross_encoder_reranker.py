"""Lazy local relevance scoring; existing chunk text and citations stay intact."""

import math

from app.config import Settings
from app.search.rerank_windows import passage_windows


class CrossEncoderReranker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as error:
                raise RuntimeError("Install embeddings: pip install -e '.[embeddings]'") from error
            self._model = CrossEncoder(
                self.settings.reranker_model,
                revision=self.settings.reranker_revision,
                cache_folder=str(self.settings.reranker_cache_dir),
                device=self.settings.reranker_device,
                max_length=512,
                trust_remote_code=False,
            )
        return self._model

    def rerank(self, query, hits, top_k):
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not hits:
            return []
        model = self._load_model()

        def count_pair(question, passage):
            return len(
                model.tokenizer(question, passage, truncation=False, verbose=False)["input_ids"]
            )

        pairs = []
        owners = []
        for index, hit in enumerate(hits):
            text = hit.chunk.text
            if hit.chunk.heading:
                text = f"Context heading: {hit.chunk.heading}\n{text}"
            for window in passage_windows(query, text, count_pair, model.max_length):
                pairs.append((query, window))
                owners.append(index)
        scores = model.predict(
            pairs, batch_size=self.settings.reranker_batch_size, show_progress_bar=False
        )
        if len(scores) != len(pairs):
            raise ValueError("Reranker returned an unexpected number of scores")
        best = {}
        for owner, raw_score in zip(owners, scores):
            score = float(raw_score)
            if not math.isfinite(score):
                raise ValueError("Reranker returned a non-finite score")
            best[owner] = max(best.get(owner, -math.inf), score)
        ranked = sorted(range(len(hits)), key=lambda index: (-best[index], index))
        return [
            hits[index].model_copy(update={"rerank_score": best[index]}) for index in ranked[:top_k]
        ]
