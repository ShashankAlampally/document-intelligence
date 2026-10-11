"""Verify the terminal chunk preview uses preparation and preserves errors."""

import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.ingestion.folder_preview import main
from app.schemas.chunks import ChunkedDocument


@pytest.mark.parametrize("broken_pdf", [False, True])
def test_chunk_cli_outputs_and_error_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    broken_pdf: bool,
) -> None:
    (tmp_path / "notice.html").write_text("<h1>Delivery</h1><p>" + "Within 45 days. " * 20 + "</p>")
    if broken_pdf:
        (tmp_path / "broken.pdf").write_text("Not a PDF")
    output = tmp_path / "chunks.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "folder_preview",
            str(tmp_path),
            "--chunks",
            "--chunk-size",
            "100",
            "--overlap",
            "10",
            "--output",
            str(output),
        ],
    )
    if broken_pdf:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 1
    else:
        main()
    results = TypeAdapter(list[ChunkedDocument]).validate_json(output.read_bytes())
    valid = next(result for result in results if result.document.source.file_type == "html")
    assert valid.document.preparation_version == 1
    assert len(valid.chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in valid.chunks)
    text = output.with_suffix(".txt").read_text()
    assert "CHUNK 1" in text
    assert "section-2" in text
    if broken_pdf:
        assert "unreadable_file" in text


def test_invalid_chunk_settings_fail_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "chunks.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "folder_preview",
            str(tmp_path),
            "--chunks",
            "--chunk-size",
            "100",
            "--overlap",
            "100",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()
