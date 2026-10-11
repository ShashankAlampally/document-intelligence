"""Check bounded splits, boundary choices, overlap, and full content coverage."""

import pytest

from app.schemas.chunks import ChunkSettings
from app.search.text_splitter import split_text


@pytest.mark.parametrize(
    "text",
    [
        "",
        "  \n ",
        "Short passage.",
        "Delivery within 45 days. " * 30,
        "A" * 40 + "\n\n" + "B" * 90,
        "https://example.com/" + "x" * 250,
        "One\n\nTwo\n\nThree " * 20,
    ],
)
@pytest.mark.parametrize("overlap", [0, 10, 49])
def test_exact_offsets_size_and_content_coverage(text: str, overlap: int) -> None:
    settings = ChunkSettings(max_chars=50, overlap_chars=overlap)
    spans = split_text(text, settings)
    covered = set()
    for span in spans:
        assert 0 < len(span.text) <= 50
        assert span.text == text[span.start : span.end]
        covered.update(range(span.start, span.end))
    assert all(index in covered for index, char in enumerate(text) if not char.isspace())
    assert all(left.start < right.start for left, right in zip(spans, spans[1:]))


def test_paragraph_boundary_is_preferred() -> None:
    text = "A" * 40 + "\n\n" + "B" * 70
    spans = split_text(text, ChunkSettings(max_chars=70, overlap_chars=10))
    assert spans[0].text == "A" * 40


def test_sentence_boundary_is_preferred_over_word_boundary() -> None:
    text = "First sentence has thirty letters. Second sentence has thirty letters. Third sentence."
    spans = split_text(text, ChunkSettings(max_chars=75, overlap_chars=10))
    assert spans[0].text.endswith("Second sentence has thirty letters.")


def test_overlap_shares_source_characters() -> None:
    text = "word " * 80
    spans = split_text(text, ChunkSettings(max_chars=60, overlap_chars=15))
    assert 0 < spans[0].end - spans[1].start <= 15


@pytest.mark.parametrize("size, overlap", [(0, 0), (20, -1), (20, 20), (20, 21)])
def test_invalid_settings_are_rejected(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        ChunkSettings(max_chars=size, overlap_chars=overlap)


def test_trailing_newline_does_not_repeat_short_span():
    text = "Question?\nAnswer: Laptops only.\n"
    spans = split_text(text, ChunkSettings(max_chars=1000, overlap_chars=100))
    assert len(spans) == 1
    assert spans[0].text == text.rstrip()
    assert text[spans[0].start : spans[0].end] == spans[0].text
