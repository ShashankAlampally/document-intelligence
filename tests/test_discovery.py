"""Verify folder discovery using temporary files, without any document parsing."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.discovery import discover_bid_files
from app.schemas.files import FileRecord


def test_supported_formats_subfolders_and_source_paths(tmp_path: Path) -> None:
    nested = tmp_path / "addendums"
    nested.mkdir()
    for name in ["original.PDF", "page.html", "extra.HTM", "photo.png", ".DS_Store"]:
        (tmp_path / name).touch()
    (nested / "original.pdf").touch()

    records = discover_bid_files(str(tmp_path))

    assert [record.relative_path.as_posix() for record in records] == [
        "addendums/original.pdf",
        "extra.HTM",
        "original.PDF",
        "page.html",
    ]
    assert [record.file_type for record in records] == ["pdf", "html", "pdf", "html"]
    assert all(record.folder_name == tmp_path.name for record in records)
    assert all(record.file_path == tmp_path / record.relative_path for record in records)
    assert all(record.file_name == record.file_path.name for record in records)
    assert len({record.discovery_id for record in records}) == 1
    assert records[0].discovery_id.version == 4


def test_repeated_discovery_gets_a_new_id(tmp_path: Path) -> None:
    (tmp_path / "original.pdf").touch()

    first = discover_bid_files(tmp_path)[0]
    second = discover_bid_files(tmp_path)[0]

    assert first.folder_name == second.folder_name
    assert first.discovery_id != second.discovery_id


def test_relative_folder_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "Bid1"
    folder.mkdir()
    (folder / "original.pdf").touch()
    monkeypatch.chdir(tmp_path)

    record = discover_bid_files("Bid1")[0]

    assert record.file_path == folder / "original.pdf"
    assert record.folder_name == "Bid1"


def test_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Folder does not exist"):
        discover_bid_files(tmp_path / "missing")


def test_file_instead_of_folder(tmp_path: Path) -> None:
    file = tmp_path / "original.pdf"
    file.touch()
    with pytest.raises(NotADirectoryError, match="Expected a folder"):
        discover_bid_files(file)


@pytest.mark.parametrize("file_name", [None, "photo.png"])
def test_no_supported_files(tmp_path: Path, file_name: str | None) -> None:
    if file_name:
        (tmp_path / file_name).touch()
    with pytest.raises(ValueError, match="No supported PDF or HTML files"):
        discover_bid_files(tmp_path)


def test_symbolic_links_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "original.pdf").touch()
    (tmp_path / "linked.pdf").symlink_to(tmp_path / "original.pdf")
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)

    assert len(discover_bid_files(tmp_path)) == 1


def test_record_rejects_unsupported_format(tmp_path: Path) -> None:
    (tmp_path / "original.pdf").touch()
    data = discover_bid_files(tmp_path)[0].model_dump()
    data["file_type"] = "png"
    with pytest.raises(ValidationError):
        FileRecord(**data)
