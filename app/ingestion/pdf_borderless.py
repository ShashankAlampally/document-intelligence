"""Recognize simple two-column layouts from repeated alignment and wide gaps.

This is a heuristic, not a general table-understanding model. Full page text is
retained by the parser even when this fallback cannot identify a table.
"""

from collections import Counter
from typing import Any

from pymupdf import Page


def _lines(page: Page) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    words = [
        {"x0": word[0], "top": word[1], "x1": word[2], "bottom": word[3], "text": word[4]}
        for word in page.get_text("words")
    ]
    for word in sorted(words, key=lambda word: (word["top"], word["x0"])):
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > 5:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [sorted(line, key=lambda word: word["x0"]) for line in lines]


def extract_borderless_rows(page: Page) -> list[list[str | None]]:
    lines = _lines(page)
    pairs = {}
    for index, line in enumerate(lines):
        gaps = [right["x0"] - left["x1"] for left, right in zip(line, line[1:])]
        if not gaps or max(gaps) < 24:
            continue
        split = gaps.index(max(gaps)) + 1
        pairs[index] = (line[:split], line[split:])

    def alignment(pair: tuple[list[dict[str, Any]], list[dict[str, Any]]], side: str) -> int:
        right = pair[1]
        coordinate = right[0]["x0"] if side == "left" else right[-1]["x1"]
        return round(round(coordinate, 2) / 8)

    if not pairs:
        return []
    counts = {
        side: Counter(alignment(pair, side) for pair in pairs.values())
        for side in ["left", "right"]
    }
    side = max(counts, key=lambda side: counts[side].most_common(1)[0][1])
    edge, count = counts[side].most_common(1)[0]
    if count < 3:
        return []
    pairs = {index: pair for index, pair in pairs.items() if alignment(pair, side) == edge}
    # Once alignment is established, keep long descriptions whose gap is smaller.
    boundary = min(right[0]["x0"] for _, right in pairs.values()) - 5
    for index, line in enumerate(lines):
        left = [word for word in line if word["x0"] < boundary]
        right = [word for word in line if word["x0"] >= boundary]
        if left and right and alignment((left, right), side) == edge:
            pairs[index] = (left, right)
    rows = []
    previous_bottom = None
    left_edge = None
    last_pair = max(pairs)
    for index in range(min(pairs), len(lines)):
        line = lines[index]
        if index in pairs:
            left, right = pairs[index]
            rows.append(
                [" ".join(word["text"] for word in left), " ".join(word["text"] for word in right)]
            )
            left_edge = left[0]["x0"]
        elif (
            rows
            and previous_bottom is not None
            and left_edge is not None
            and line[0]["top"] - previous_bottom < 12
            and abs(line[0]["x0"] - left_edge) < 8
        ):
            rows[-1][0] += "\n" + " ".join(word["text"] for word in line)
        elif index > last_pair:
            break
        previous_bottom = max(word["bottom"] for word in line)
    return rows
