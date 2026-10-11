"""Check conservative role labels and metadata propagation without model calls."""

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.ingestion.document_metadata import classify_source
from app.ingestion.pipeline import parse_folder
from app.schemas.metadata import SourceMetadata


def source(name="document.pdf", **values):
    return SourceMetadata(
        discovery_id=uuid4(),
        folder_name="Example",
        file_name=name,
        file_path=Path("/example") / name,
        relative_path=Path(name),
        file_type="html" if name.endswith(".html") else "pdf",
        **values,
    )


@pytest.mark.parametrize(
    "name,role,number",
    [
        ("Addendum 1 RFP.pdf", "addendum", 1),
        ("ADDENDUM_02.pdf", "addendum", 2),
        ("Addendum No. 3.pdf", "addendum", 3),
        ("Addendum #4.pdf", "addendum", 4),
        ("Addendum.pdf", "addendum", None),
        ("Addendum 0.pdf", "addendum", None),
        ("RFP 123.pdf", "rfp", None),
        ("PORFP_-_Laptop.pdf", "rfp", None),
        ("Laptop_Specs.pdf", "specs", None),
        ("Contract_Affidavit.pdf", "affidavit", None),
        ("Bid Information.html", "bid_page", None),
        ("random.pdf", "unknown", None),
    ],
)
def test_filename_labels(name, role, number):
    result = classify_source(source(name))
    assert result.doc_type == role
    assert result.addendum_number == number


def test_opening_heading_can_identify_generic_filename():
    result = classify_source(source(), "Addendum 2\nSubmission deadline extended")
    assert result.doc_type == "addendum"
    assert result.addendum_number == 2


def test_department_header_before_rfp_heading():
    result = classify_source(
        source(), "PURCHASING DEPARTMENT\nOffice address\nPhone number\nRequest For Proposal 123"
    )
    assert result.doc_type == "rfp"


def test_body_reference_does_not_make_original_an_addendum():
    result = classify_source(source(), "General terms\nPlease acknowledge Addendum 2")
    assert result.doc_type == "unknown"
    assert result.addendum_number is None


def test_explicit_metadata_and_identity_are_preserved():
    original = source(
        "Addendum 1.pdf",
        doc_type="addendum",
        addendum_number=8,
        document_date=date(2024, 6, 1),
    )
    result = classify_source(original)
    assert result.addendum_number == 8
    assert result.document_date == original.document_date
    assert result.discovery_id == original.discovery_id
    assert result.file_path == original.file_path
    assert original.addendum_number == 8


def test_submission_date_is_not_inferred_as_document_date():
    result = classify_source(source("RFP.pdf"), "Submission deadline June 10, 2024")
    assert result.document_date is None


def test_folder_pipeline_labels_documents_before_chunking(tmp_path):
    (tmp_path / "Addendum 2.html").write_text("<h1>Addendum 2</h1><p>Deadline extended</p>")
    result = parse_folder(tmp_path)[0]
    assert result.source.doc_type == "addendum"
    assert result.source.addendum_number == 2
    assert result.text_blocks[0].text == "Addendum 2\nDeadline extended"
