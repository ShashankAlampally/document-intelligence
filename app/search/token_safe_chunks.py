"""Split oversized chunks using the provider's actual tokenizer, preserving sources."""

from collections.abc import Callable
from uuid import uuid5

from app.schemas.chunks import Chunk, ChunkSettings
from app.search.table_chunks import row_chunk
from app.search.text_splitter import split_text


def fit_chunks_to_tokens(
    chunks: list[Chunk], count_tokens: Callable[[str], int], max_tokens: int
) -> list[Chunk]:
    def fit(chunk: Chunk) -> list[Chunk]:
        if count_tokens(chunk.text) <= max_tokens:
            return [chunk]
        if chunk.table_id is not None and len(chunk.table_rows) > 1:
            middle = len(chunk.table_rows) // 2
            left = row_chunk(chunk, chunk.table_rows[:middle], chunk.table_row_start)
            right = row_chunk(chunk, chunk.table_rows[middle:], chunk.table_row_start + middle)
            return fit(left) + fit(right)
        if len(chunk.text) == 1:
            raise ValueError("A single character exceeds the embedding model token limit")
        # Smaller character windows guarantee progress; actual tokens are checked again.
        size = max(1, len(chunk.text) // 2)
        settings = ChunkSettings(max_chars=size, overlap_chars=min(100, size // 5))
        result = []
        for span in split_text(chunk.text, settings):
            start = chunk.start_char + span.start
            end = chunk.start_char + span.end
            identity = (
                f"{chunk.source.relative_path.as_posix()}|{chunk.extraction_method}|"
                f"{chunk.content_type}|{chunk.block_index}|{start}|{end}|{span.text}"
            )
            if chunk.table_id is not None:
                # Oversized single rows use embedding fragments, retaining full
                # row data for reconstruction rather than discarding cell text.
                identity += f"|{chunk.table_id}|{chunk.table_row_start}|{chunk.table_row_end}"
            child = chunk.model_copy(
                deep=True,
                update={
                    "chunk_id": uuid5(chunk.source.discovery_id, identity),
                    "text": span.text,
                    "start_char": start,
                    "end_char": end,
                },
            )
            result.extend(fit(child))
        return result

    # Adjacent overlapping parents can generate identical spans; store each once.
    fitted = {}
    for chunk in chunks:
        for child in fit(chunk):
            fitted[child.chunk_id] = child
    return list(fitted.values())
