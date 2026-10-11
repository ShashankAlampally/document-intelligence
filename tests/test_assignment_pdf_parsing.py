"""Protect important facts in the actual assignment PDFs without model calls."""

import re
from pathlib import Path

import pymupdf
import pytest

from app.config import PROJECT_ROOT
from app.ingestion.pdf_tables import extract_pdf_tables

DATA = PROJECT_ROOT / "Assignment-Data-Statements (AI Engineer-Emplay Inc)"


def open_assignment(relative_path: str):
    path = DATA / Path(relative_path)
    if not path.exists():
        pytest.skip("Assignment sample files are not present")
    return pymupdf.open(path)


def test_bid1_monitor_quantities_survive_table_extraction():
    with open_assignment("Bid1/JA-207652 Student and Staff Computing Devices FINAL.pdf") as pdf:
        tables = extract_pdf_tables(pdf[34], 35)
        rows = [row for table in tables for row in table.rows]
    monitors = [row for row in rows if "Display Monitor" in " ".join(cell or "" for cell in row)]
    assert len(monitors) == 2
    assert all("5,000" in row for row in monitors)
    assert any("Non-Touch" in " ".join(cell or "" for cell in row) for row in monitors)


def test_bid1_staff_tiers_and_buyer_remain_in_page_text():
    with open_assignment("Bid1/JA-207652 Student and Staff Computing Devices FINAL.pdf") as pdf:
        buyer = pdf[1].get_text("text", sort=True)
        specs = re.sub(r"\s+", " ", pdf[5].get_text("text", sort=True))
    assert "JALZATE@dallasisd.org" in buyer
    assert "JA-207652" in buyer
    assert "512 GB NVMe SSD" in specs
    assert "32GB DDR5 RAM" in specs
    assert "1 TB NVMe SSD" in specs


def test_porfp_product_quantities_survive_irregular_table():
    with open_assignment("Bid2/PORFP_-_Dell_Laptop_Final.pdf") as pdf:
        tables = extract_pdf_tables(pdf[2], 3)
        rows = [row for table in tables for row in table.rows]
    laptop = [row for row in rows if "Latitude" in " ".join(cell or "" for cell in row)]
    dock = [row for row in rows if "WD22TB4" in " ".join(cell or "" for cell in row)]
    assert laptop and dock
    assert any("30" in row for row in laptop)
    assert any("30" in row for row in dock)
