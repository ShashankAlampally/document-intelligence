"""Check HTML content retention, table geometry, and recoverable failures."""

from pathlib import Path

import pytest

from app.ingestion import html_parser
from app.ingestion.discovery import discover_bid_files
from app.schemas.documents import ParsedDocument


def parse_markup(tmp_path: Path, markup: str) -> ParsedDocument:
    (tmp_path / "bid.html").write_text(markup, encoding="utf-8")
    return html_parser.parse_html(discover_bid_files(tmp_path)[0])


def test_sections_source_and_non_content_removal(tmp_path: Path) -> None:
    result = parse_markup(
        tmp_path,
        "<head><title>Hidden title</title></head><body>Introduction"
        "<h1>Bid &amp; details</h1><div>Quantity <b>30</b></div>"
        "<h2>Dates</h2><p>Closing: July 9</p><script>script noise</script>"
        "<style>style noise</style><template>template noise</template>"
        "<div hidden>hidden noise</div><!-- comment noise --></body>",
    )
    assert [block.section for block in result.text_blocks] == [
        "section-1",
        "section-2",
        "section-3",
    ]
    assert result.text_blocks[1].heading == "Bid & details"
    assert "Quantity\n30" in result.text_blocks[1].text
    assert "Closing: July 9" in result.text_blocks[2].text
    assert "noise" not in " ".join(block.text for block in result.text_blocks)
    assert result.page_count is None
    assert all(block.page_number is None for block in result.text_blocks)
    assert result.source.file_name == "bid.html"
    assert result.source.doc_type == "unknown"
    assert ParsedDocument.model_validate_json(result.model_dump_json()) == result


def test_table_spans_caption_and_empty_cells(tmp_path: Path) -> None:
    result = parse_markup(
        tmp_path,
        '<h1>Items</h1><table><caption>Order</caption><tr><th colspan="2">Devices</th></tr>'
        '<tr><td rowspan="2">Laptop</td><td>30</td></tr><tr><td></td></tr></table>',
    )
    table = result.tables[0]
    assert table.section == "section-2"
    assert table.caption == "Order"
    assert table.headers == []
    assert table.rows == [["Devices", None], ["Laptop", "30"], [None, None]]
    assert result.issues == []


def test_non_utf8_declared_encoding(tmp_path: Path) -> None:
    path = tmp_path / "bid.html"
    path.write_bytes('<meta charset="windows-1252"><p>Café £30</p>'.encode("cp1252"))
    result = html_parser.parse_html(discover_bid_files(tmp_path)[0])
    assert "Café £30" in result.text_blocks[0].text


def test_imperfect_markup_preserves_text(tmp_path: Path) -> None:
    result = parse_markup(tmp_path, "<h1>Bid<p>Delivery within 45 days")
    assert "Delivery within 45 days" in result.text_blocks[0].text
    assert not any(issue.severity == "error" for issue in result.issues)


def test_images_are_flagged_without_preventing_text(tmp_path: Path) -> None:
    result = parse_markup(tmp_path, '<p>Readable terms</p><img src="remote.png">')
    assert result.text_blocks[0].text == "Readable terms"
    assert result.issues[0].code == "image_content_not_read"


def test_empty_html_is_flagged(tmp_path: Path) -> None:
    result = parse_markup(tmp_path, "<body><script>noise</script></body>")
    assert result.text_blocks == []
    assert result.issues[0].code == "no_text_extracted"


def test_unreadable_file_returns_error(tmp_path: Path) -> None:
    path = tmp_path / "bid.html"
    path.touch()
    record = discover_bid_files(tmp_path)[0]
    path.unlink()
    result = html_parser.parse_html(record)
    assert result.issues[0].code == "unreadable_file"
    assert result.issues[0].severity == "error"


def test_non_html_record_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bid.pdf").touch()
    with pytest.raises(ValueError, match="HTML file record"):
        html_parser.parse_html(discover_bid_files(tmp_path)[0])


@pytest.mark.parametrize(
    "table",
    [
        '<table><tr><td rowspan="0">Terms</td></tr></table>',
        "<table><tr><td>Terms<table><tr><td>Nested</td></tr></table></td></tr></table>",
    ],
)
def test_problematic_table_keeps_raw_text(tmp_path: Path, table: str) -> None:
    result = parse_markup(tmp_path, table + "<h2>Later</h2><p>Deadline July 9</p>")
    assert any(issue.code == "table_extraction_failed" for issue in result.issues)
    assert "Terms" in result.text_blocks[0].text
    assert "Deadline July 9" in result.text_blocks[-1].text


def test_table_failure_does_not_stop_other_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = html_parser.extract_html_table

    def extract(table, section):
        if table.get("id") == "broken":
            raise RuntimeError("table failure")
        return original(table, section)

    monkeypatch.setattr(html_parser, "extract_html_table", extract)
    result = parse_markup(
        tmp_path,
        '<table id="broken"><tr><td>Retained</td></tr></table>'
        "<table><tr><td>Laptop</td><td>30</td></tr></table>",
    )
    assert result.tables[0].rows == [["Laptop", "30"]]
    assert "Retained" in result.text_blocks[0].text
    assert result.issues[0].code == "table_extraction_failed"
