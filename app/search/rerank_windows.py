"""Fit question/passage pairs without silently truncating evidence or the question."""

from app.schemas.chunks import ChunkSettings
from app.search.text_splitter import split_text


def passage_windows(query, text, count_pair, max_tokens):
    if count_pair(query, "") >= max_tokens:
        raise ValueError("Question exceeds the reranker's token budget")
    if count_pair(query, text) <= max_tokens:
        return [text]
    if len(text) <= 1:
        raise ValueError("Question leaves no token space for the passage")
    size = max(1, len(text) // 2)
    settings = ChunkSettings(max_chars=size, overlap_chars=min(100, size // 5))
    windows = []
    for span in split_text(text, settings):
        windows.extend(passage_windows(query, span.text, count_pair, max_tokens))
    return windows
