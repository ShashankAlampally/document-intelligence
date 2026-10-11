"""Check saved folder previews and useful failure exit status."""

import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.ingestion.folder_preview import main
from app.schemas.documents import ParsedDocument


@pytest.mark.parametrize("broken_pdf", [False, True])
@pytest.mark.parametrize("prepare", [False, True])
def test_preview_saves_results_including_file_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    broken_pdf: bool,
    prepare: bool,
) -> None:
    folder = tmp_path / "input"
    folder.mkdir()
    (folder / "notice.html").write_text("<h1>Dates</h1><p>Closing   July 9</p>")
    if broken_pdf:
        (folder / "broken.pdf").write_text("Not a PDF")
    output = tmp_path / "outputs" / "preview.json"
    argv = ["folder_preview", str(folder), "--output", str(output)]
    if prepare:
        argv.append("--prepare")
    monkeypatch.setattr(sys, "argv", argv)
    if broken_pdf:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 1
    else:
        main()
    documents = TypeAdapter(list[ParsedDocument]).validate_json(output.read_bytes())
    assert len(documents) == (2 if broken_pdf else 1)
    import json

    saved = json.loads(output.read_text())
    assert all((doc.get("preparation_version") == 1) == prepare for doc in saved)
    text = output.with_suffix(".txt").read_text()
    assert "Closing July 9" in text
    assert "SECTION section-2" in text
    if broken_pdf:
        assert "unreadable_file" in text


def test_missing_folder_produces_cli_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "output.json"
    monkeypatch.setattr(
        sys, "argv", ["folder_preview", str(tmp_path / "missing"), "--output", str(output)]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()
