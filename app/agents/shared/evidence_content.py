"""Compare passage content without confusing different source documents."""

import json
import re
from difflib import SequenceMatcher


def normalized_text(item):
    text = item["text"]
    try:
        table = json.loads(text)
        if isinstance(table, dict) and "rows" in table:
            cells = [cell for row in table["rows"] for cell in row if cell]
            text = " ".join(str(cell) for cell in cells)
    except (ValueError, TypeError):
        pass
    return " ".join(re.findall(r"\w+", text.casefold()))


def same_content(left, right):
    # Never merge original/addendum evidence or independently stated facts.
    location = ("discovery_id", "file_name", "page_number", "section")
    if any(left.get(key) != right.get(key) for key in location):
        return False
    a, b = normalized_text(left), normalized_text(right)
    if a == b:
        return True
    if min(len(a), len(b)) >= 100 and a in b:
        return True
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return False
    if left.get("heading_context") != right.get("heading_context"):
        return False
    if min(len(a), len(b)) < 100:
        return False
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.92


def model_evidence(item):
    """Scores are diagnostics, not evidence; retain them in the retrieval trace."""
    scores = {
        "similarity",
        "retrieval_score",
        "rerank_score",
        "keyword_score",
        "vector_rank",
        "keyword_rank",
    }
    return {key: value for key, value in item.items() if key not in scores}
