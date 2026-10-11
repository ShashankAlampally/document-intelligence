"""Verify reference isolation and resumable evaluation without provider calls."""

from types import SimpleNamespace
from zipfile import ZipFile

from scripts.evaluate_qa import run_questions
from scripts.qa_reference import read_pairs


def test_read_pairs_keeps_table_text_and_separates_evidence(tmp_path):
    path = tmp_path / "pairs.docx"
    xml = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body><w:p><w:r><w:t>Q1. What quantity?</w:t></w:r></w:p>
    <w:p><w:r><w:t>Answer:</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>50,000</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:p><w:r><w:t>Evidence:</w:t></w:r></w:p>
    <w:p><w:r><w:t>RFP p.35</w:t></w:r></w:p></w:body></w:document>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
    pair = read_pairs(path)[0]
    assert pair["question"] == "What quantity?"
    assert pair["reference_answer"].strip() == "50,000"
    assert "RFP p.35" in pair["reference_evidence"]


def test_run_only_sends_question_and_skips_success_on_resume(tmp_path, monkeypatch):
    calls = []

    def answer(question, model, tools):
        calls.append(question)
        return SimpleNamespace(
            status="found",
            error=None,
            trace=[],
            model_dump=lambda: dict(status="found", answer="Generated", sources=[], trace=[]),
        )

    monkeypatch.setattr("scripts.evaluate_qa.answer_question", answer)
    record = dict(
        status="prepared",
        pairs=[
            dict(
                id=1,
                question="QUESTION",
                reference_answer="SECRET REFERENCE",
                reference_evidence="REFERENCE",
            )
        ],
        results=[],
    )
    run_questions(record, tmp_path, None, None)
    run_questions(record, tmp_path, None, None)
    assert calls == ["QUESTION"]
    assert record["status"] == "completed"
    assert (tmp_path / "results.json").exists()
