"""Test embedding CLI output and failures without loading a real model."""

import json
import sys
from pathlib import Path

import pytest

from app.schemas.embeddings import EmbeddingInfo, EmbeddingResult
from app.search import embedding_preview


class PreviewProvider:
    info = EmbeddingInfo(
        provider="test",
        model="test",
        revision="test",
        dimensions=2,
        max_tokens=100,
        library_version="test",
    )

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [0.0, 1.0]


@pytest.mark.parametrize("broken_pdf", [False, True])
def test_preview_retains_evidence_and_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    broken_pdf: bool,
) -> None:
    (tmp_path / "notice.html").write_text("<h1>Delivery</h1><p>Within 45 days</p>")
    if broken_pdf:
        (tmp_path / "broken.pdf").write_text("Not a PDF")
    output = tmp_path / "embeddings.json"
    monkeypatch.setattr(embedding_preview, "LocalEmbeddingProvider", PreviewProvider)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "embedding_preview",
            str(tmp_path),
            "--output",
            str(output),
            "--query",
            "When is delivery?",
        ],
    )
    if broken_pdf:
        with pytest.raises(SystemExit) as error:
            embedding_preview.main()
        assert error.value.code == 1
    else:
        embedding_preview.main()
    payload = json.loads(output.read_text())
    result = EmbeddingResult.model_validate(payload["embedding_result"])
    assert result.query.text == "When is delivery?"
    assert all(len(record.vector) == 2 for record in result.embeddings)
    assert len(payload["documents"]) == (2 if broken_pdf else 1)
    assert "Vector sample" in output.with_suffix(".txt").read_text()
    if broken_pdf:
        assert any(doc["document"]["issues"] for doc in payload["documents"])


def test_embedding_failure_does_not_write_partial_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingProvider(PreviewProvider):
        def embed_documents(self, texts):
            raise ValueError("Token limit exceeded")

    (tmp_path / "notice.html").write_text("<p>Text</p>")
    output = tmp_path / "embeddings.json"
    monkeypatch.setattr(embedding_preview, "LocalEmbeddingProvider", FailingProvider)
    monkeypatch.setattr(sys, "argv", ["embedding_preview", str(tmp_path), "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        embedding_preview.main()
    assert error.value.code == 1
    assert not output.exists()
