"""Dense text must fit the model without dropping content or losing citations."""

from test_embeddings import chunks as example_chunks

from app.search.token_safe_chunks import fit_chunks_to_tokens


def dense_chunk(text):
    return example_chunks()[0].model_copy(
        update={"text": text, "start_char": 20, "end_char": 20 + len(text)}
    )


def test_safe_chunk_keeps_id_and_oversized_text_is_fully_covered():
    safe = dense_chunk("abc")
    dense = dense_chunk("漢字_123-" * 150)

    def counter(text):
        return len(text) * 3 + 2

    fitted = fit_chunks_to_tokens([safe, dense], counter, 512)
    assert fitted[0].chunk_id == safe.chunk_id
    children = fitted[1:]
    assert len(children) > 1
    covered = set()
    for child in children:
        assert counter(child.text) <= 512
        assert child.source == dense.source
        assert child.page_number == dense.page_number
        assert child.block_index == dense.block_index
        start, end = child.start_char - 20, child.end_char - 20
        assert dense.text[start:end] == child.text
        covered.update(range(start, end))
    assert covered == set(range(len(dense.text)))
    assert [chunk.chunk_id for chunk in fitted] == [
        chunk.chunk_id for chunk in fit_chunks_to_tokens([safe, dense], counter, 512)
    ]


def test_recursive_splits_cover_words_without_blank_chunks():
    original = dense_chunk("Long delivery specification. " * 100)
    fitted = fit_chunks_to_tokens([original], lambda text: len(text.split()) + 2, 15)
    covered = set()
    for chunk in fitted:
        assert len(chunk.text.split()) + 2 <= 15
        covered.update(range(chunk.start_char - 20, chunk.end_char - 20))
    assert all(index in covered for index, char in enumerate(original.text) if not char.isspace())
