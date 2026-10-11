"""Split strings with bounded size, approximate overlap, and exact source offsets."""

import re
from dataclasses import dataclass

from app.schemas.chunks import ChunkSettings


@dataclass(frozen=True)
class TextSpan:
    text: str
    start: int
    end: int


def _end_boundary(text: str, start: int, limit: int, settings: ChunkSettings) -> int:
    if limit == len(text):
        return limit
    # Prefer late boundaries so chunks are useful and the overlap makes progress.
    minimum = start + max(settings.max_chars // 2, settings.overlap_chars + 1)
    window = text[start:limit]
    for pattern in (r"\n\n", r"[.!?][\"')\]]?(?=\s)", r"\s+"):
        ends = [start + match.end() for match in re.finditer(pattern, window)]
        suitable = [end for end in ends if minimum <= end <= limit]
        if suitable:
            return suitable[-1]
    return limit  # Oversized words/URLs need a hard character split.


def split_text(text: str, settings: ChunkSettings) -> list[TextSpan]:
    """Keep all non-whitespace content in order, within a hard character limit.

    Overlap is up to overlap_chars, adjusted forward to a word boundary where
    possible. Very long unbroken strings use character splits. Offsets refer to
    the input string; trimming whitespace also adjusts the returned offsets.
    """
    spans = []
    start = 0
    while start < len(text):
        while start < len(text) and text[start].isspace():
            start += 1
        if start == len(text):
            break
        end = _end_boundary(text, start, min(start + settings.max_chars, len(text)), settings)
        reached_end = end == len(text)
        while end > start and text[end - 1].isspace():
            end -= 1
        spans.append(TextSpan(text=text[start:end], start=start, end=end))
        if reached_end:
            break
        next_start = max(start + 1, end - settings.overlap_chars)
        if next_start < end and not text[next_start - 1].isspace():
            boundary = re.search(r"\s+", text[next_start:end])
            if boundary:
                next_start += boundary.end()
        start = next_start
    return spans
