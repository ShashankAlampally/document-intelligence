"""Local embedding provider with explicit query instruction and no silent truncation."""

from importlib.metadata import version
from time import perf_counter

from app.config import Settings
from app.schemas.embeddings import EmbeddingInfo


class LocalEmbeddingProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "Install embedding dependencies: pip install -e '.[embeddings]'"
                ) from error
            started = perf_counter()
            print(
                f"Loading embedding model: {self.settings.embedding_model} "
                "(downloads on first use)...",
                flush=True,
            )
            self._model = SentenceTransformer(
                self.settings.embedding_model,
                revision=self.settings.embedding_revision,
                cache_folder=str(self.settings.embedding_cache_dir),
                device=self.settings.embedding_device,
                trust_remote_code=False,
                truncate_dim=self.settings.embedding_dimensions,
                model_kwargs={"torch_dtype": "auto"},
            )
            print(f"Embedding model ready in {perf_counter() - started:.1f}s", flush=True)
        return self._model

    @property
    def info(self) -> EmbeddingInfo:
        model = self._load_model()
        return EmbeddingInfo(
            provider="sentence-transformers",
            model=self.settings.embedding_model,
            revision=self.settings.embedding_revision,
            dimensions=min(
                self.settings.embedding_dimensions, model.get_sentence_embedding_dimension()
            ),
            max_tokens=model.max_seq_length,
            normalized=True,
            query_prefix=self.settings.embedding_query_prefix,
            library_version=version("sentence-transformers"),
        )

    def count_tokens(self, text: str) -> int:
        """Include special tokens and count without truncation or warning-only overflow."""
        tokenizer = self._load_model().tokenizer
        return len(
            tokenizer(
                text,
                truncation=False,
                add_special_tokens=True,
                return_attention_mask=False,
                verbose=False,
            )["input_ids"]
        )

    def _encode(self, texts: list[str], label: str) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("Embedding inputs cannot be empty or whitespace-only")
        model = self._load_model()
        for index, text in enumerate(texts):
            token_count = self.count_tokens(text)
            if token_count > model.max_seq_length:
                raise ValueError(
                    f"{label} input {index + 1} has {token_count} tokens; model limit is "
                    f"{model.max_seq_length}. Shorten the query or split document chunks. "
                    "No text was truncated."
                )
        return model.encode(
            texts,
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=label == "Document" and len(texts) > 1,
            prompt="",
        ).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, "Document")

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query cannot be empty or whitespace-only")
        return self._encode([self.settings.embedding_query_prefix + text.strip()], "Query")[0]
