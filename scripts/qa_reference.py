"""Read numbered Q/Answer/Evidence blocks without sending references to QA."""

import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def read_pairs(path: Path) -> list[dict]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    pairs = []
    current = None
    section = None
    for paragraph in root.findall(".//w:body//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        if not text:
            continue
        match = re.match(r"^Q(\d+)\.\s+(.+)$", text)
        if match:
            current = dict(
                id=int(match[1]), question=match[2], reference_answer="", reference_evidence=""
            )
            pairs.append(current)
            section = None
        elif current is not None:
            if text.startswith("Answer:"):
                section = "reference_answer"
                text = text.removeprefix("Answer:").strip()
            elif text.startswith("Evidence"):
                section = "reference_evidence"
            if section and text:
                current[section] += text + "\n"
    if not pairs or len({pair["id"] for pair in pairs}) != len(pairs):
        raise ValueError("Expected unique numbered Q1. question / Answer: blocks")
    if any(not pair["reference_answer"].strip() for pair in pairs):
        raise ValueError("Every question needs a reference answer")
    return pairs
