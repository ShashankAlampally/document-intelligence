"""Verify folder routing, run identity, and isolation of file-level failures."""

from pathlib import Path

import pytest

from app.ingestion import pipeline
from app.schemas.documents import ParsedDocument
from app.schemas.files import FileRecord


def test_mixed_folder_routes_real_parsers_and_retains_sources(
    sample_pdf: FileRecord,
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "notice.htm").write_text("<h1>Notice</h1><p>Deadline July 9</p>")
    (tmp_path / "ignored.txt").write_text("Not a supported document")
    documents = pipeline.parse_folder(tmp_path)
    assert [doc.source.relative_path.as_posix() for doc in documents] == [
        "nested/notice.htm",
        "sample.pdf",
    ]
    assert len({doc.source.discovery_id for doc in documents}) == 1
    assert all(doc.source.folder_name == tmp_path.name for doc in documents)
    assert documents[0].page_count is None
    assert documents[0].text_blocks[0].section == "section-2"
    assert "Deadline July 9" in documents[0].text_blocks[0].text
    assert documents[1].page_count == 3
    assert "Delivery within 45 days" in documents[1].text_blocks[0].text
    assert documents[1].images and documents[1].tables
    assert all(
        ParsedDocument.model_validate_json(doc.model_dump_json()) == doc for doc in documents
    )
    assert not list(tmp_path.glob("*.json"))


def test_corrupt_pdf_does_not_stop_valid_html(tmp_path: Path) -> None:
    (tmp_path / "a_broken.pdf").write_text("Not a PDF")
    (tmp_path / "b_notice.html").write_text("<p>Valid terms</p>")
    documents = pipeline.parse_folder(tmp_path)
    assert len(documents) == 2
    assert documents[0].issues[0].severity == "error"
    assert documents[1].text_blocks[0].text == "Valid terms"


def test_unexpected_parser_exception_does_not_stop_later_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a_failed.html").write_text("<p>First</p>")
    (tmp_path / "b_valid.html").write_text("<p>Second</p>")
    original = pipeline.parse_html

    def parse(record):
        if record.file_name == "a_failed.html":
            raise RuntimeError("Unexpected failure")
        return original(record)

    monkeypatch.setattr(pipeline, "parse_html", parse)
    documents = pipeline.parse_folder(tmp_path)
    assert documents[0].issues[0].code == "parser_failed"
    assert documents[0].issues[0].message == "Unexpected failure"
    assert documents[1].text_blocks[0].text == "Second"
    assert documents[0].source.discovery_id == documents[1].source.discovery_id


def test_repeated_folder_processing_has_new_run_id(tmp_path: Path) -> None:
    (tmp_path / "notice.html").write_text("<p>Terms</p>")
    first = pipeline.parse_folder(tmp_path)[0].source
    second = pipeline.parse_folder(tmp_path)[0].source
    assert first.folder_name == second.folder_name
    assert first.discovery_id != second.discovery_id


def test_invalid_folder_raises_to_caller(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        pipeline.parse_folder(tmp_path / "missing")
    with pytest.raises(ValueError, match="No supported"):
        pipeline.parse_folder(tmp_path)
    file = tmp_path / "file.html"
    file.touch()
    with pytest.raises(NotADirectoryError):
        pipeline.parse_folder(file)
