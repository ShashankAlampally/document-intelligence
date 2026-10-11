"""Source boundaries and bounded addendum continuation regressions."""

from types import SimpleNamespace

from app.search.heading_context import build_heading_context
from app.search.qa_context import question_continuations


def chunk(identity, text, *, page=1, start=0, upload="one", role="addendum", kind="text"):
    return SimpleNamespace(
        chunk_id=identity,
        text=text,
        page_number=page,
        start_char=start,
        end_char=start + len(text),
        block_index=0,
        content_type=kind,
        source=SimpleNamespace(discovery_id=upload, file_name="same.pdf", doc_type=role),
    )


def test_following_official_answer_is_recovered_without_table_expansion_or_other_uploads():
    question = chunk("q", "What price belongs on line 11?")
    wrong = chunk("other-upload", "Submit a different price.", start=30, upload="two")
    table = chunk("table", "Entire large table", start=30, kind="table")
    answer = chunk("a", "Submit a minimum price and attach additional pricing.", start=30)
    later = chunk("later", "Another requirement", start=90)
    found = question_continuations([dict(chunk_id="q")], [question, wrong, table, answer, later])
    assert [(c.chunk_id, seed) for c, seed in found] == [("a", "q")]


def test_already_selected_answer_is_not_duplicated():
    q = chunk("q", "What warranty?")
    a = chunk("a", "One year.", start=15)
    assert question_continuations([dict(chunk_id="q"), dict(chunk_id="a")], [q, a]) == []


def test_no_context_is_carried_from_another_upload_with_same_filename():
    a = chunk("a", "Desktop Minimum Requirements\nCPU i7", upload="one", role="rfp")
    b = chunk("b", "Touchscreen optional", page=2, upload="two", role="rfp")
    assert "b" not in build_heading_context([a, b])


def test_heading_before_chunk_start_is_desktop_even_when_laptop_starts_inside_chunk():
    desktop = chunk("desktop", "Staff Desktop Minimum Requirements\nCPU i7", page=5)
    mixed = chunk(
        "mixed", "Touchscreen optional\nStaff Laptop Minimum Requirements\nCPU i5", page=6
    )
    context = build_heading_context([desktop, mixed])
    assert context["mixed"]["heading"] == "Staff Desktop Minimum Requirements"
