"""Exercise local embedding adapter behavior using a tiny tokenizer/model double."""

import pytest

from app.config import Settings
from app.search.local_embeddings import LocalEmbeddingProvider


class Output:
    def __init__(self, texts):
        self.texts = texts

    def tolist(self):
        return [[1.0, 0.0] for _ in self.texts]


class Model:
    max_seq_length = 20

    def __init__(self):
        self.calls = []

    def tokenizer(self, text, **kwargs):
        assert kwargs["truncation"] is False
        assert kwargs["add_special_tokens"] is True
        return {"input_ids": list(range(len(text.split()) + 2))}

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        return Output(texts)


def provider() -> LocalEmbeddingProvider:
    result = LocalEmbeddingProvider(Settings(_env_file=None, embedding_query_prefix="Find: "))
    result._model = Model()
    return result


def test_documents_and_queries_use_distinct_preprocessing() -> None:
    local = provider()
    assert local.embed_documents(["Delivery terms"]) == [[1.0, 0.0]]
    assert local.embed_query(" When is delivery? ") == [1.0, 0.0]
    assert local._model.calls[0][0] == ["Delivery terms"]
    assert local._model.calls[1][0] == ["Find: When is delivery?"]
    options = local._model.calls[0][1]
    assert options["normalize_embeddings"] is True
    assert options["batch_size"] == 4
    assert options["prompt"] == ""


def test_all_lengths_checked_before_any_encoding() -> None:
    local = provider()
    with pytest.raises(ValueError, match="No text was truncated"):
        local.embed_documents(["Valid", "long " * 19])
    assert local._model.calls == []


def test_query_prefix_counts_toward_limit() -> None:
    local = provider()
    with pytest.raises(ValueError, match="Query input"):
        local.embed_query("word " * 18)
    assert local._model.calls == []


def test_empty_inputs_do_not_load_model() -> None:
    local = LocalEmbeddingProvider(Settings(_env_file=None))
    assert local.embed_documents([]) == []
    assert local._model is None
    with pytest.raises(ValueError):
        local.embed_documents([" "])
    with pytest.raises(ValueError):
        local.embed_query(" ")
    assert local._model is None


def test_model_loaded_once_with_fixed_revision(tmp_path, monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    calls = []

    def load(name, **kwargs):
        calls.append((name, kwargs))
        return Model()

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=load)
    )
    local = LocalEmbeddingProvider(Settings(_env_file=None, embedding_cache_dir=tmp_path))
    local.embed_documents(["First"])
    local.embed_documents(["Second"])
    assert len(calls) == 1
    assert calls[0][0] == "BAAI/bge-large-en-v1.5"
    assert calls[0][1]["revision"] == "d4aa6901d3a41ba39fb536a557fa166f842b0e09"
    assert calls[0][1]["cache_folder"] == str(tmp_path)
    assert calls[0][1]["trust_remote_code"] is False
    assert calls[0][1]["truncate_dim"] == 1024
    assert calls[0][1]["model_kwargs"] == {"torch_dtype": "auto"}


def test_bge_defaults_use_configured_1024_dimensions_and_instruction():
    local = LocalEmbeddingProvider(Settings(_env_file=None))
    model = Model()
    model.max_seq_length = 512
    model.get_sentence_embedding_dimension = lambda: 1024
    local._model = model
    assert local.info.dimensions == 1024
    assert local.info.max_tokens == 512
    assert local.settings.vector_collection == "rfp_chunks_bge_large_1024"
    local.embed_query("What is the submission deadline?")
    query = model.calls[0][0][0]
    assert query == local.settings.embedding_query_prefix + "What is the submission deadline?"
    assert local.settings.embedding_query_prefix.startswith("Represent this sentence")
    local.embed_documents(["Deadline: July 9."])
    assert model.calls[1][0] == ["Deadline: July 9."]


def test_real_library_truncates_and_normalizes_documents_and_questions(monkeypatch):
    import math

    from sentence_transformers import SentenceTransformer, models

    # Exercise the real library with an in-memory model; no model download/API call.
    vocabulary = ["delivery", "deadline"] + [f"word{i}" for i in range(2558)]
    model = SentenceTransformer(modules=[models.BoW(vocabulary)], truncate_dim=1024)
    model[0].max_seq_length = 32768
    local = LocalEmbeddingProvider(Settings(_env_file=None, embedding_query_prefix="Query: "))
    local._model = model
    monkeypatch.setattr(local, "count_tokens", lambda text: len(text.split()) + 2)
    document = local.embed_documents(["delivery deadline"])[0]
    question = local.embed_query("delivery deadline")
    assert len(document) == len(question) == local.info.dimensions == 1024
    for vector in [document, question]:
        assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)
