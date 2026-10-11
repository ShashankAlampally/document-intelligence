"""Recover nearby explicit specification headings from already stored text."""

import re

HEADING = re.compile(r"^\s*([^\n]{3,120}Minimum Requirements)\s*$", re.MULTILINE | re.I)


def build_heading_context(chunks):
    documents = {}
    for chunk in chunks:
        if chunk.content_type == "text" and chunk.page_number is not None:
            document = (getattr(chunk.source, "discovery_id", None), chunk.source.file_name)
            documents.setdefault(document, []).append(chunk)
    context = {}
    for passages in documents.values():
        headings = {}
        for chunk in passages:
            for match in HEADING.finditer(chunk.text):
                position = (
                    chunk.page_number,
                    getattr(chunk, "block_index", 0),
                    chunk.start_char + match.start(),
                )
                headings[position] = (match.group(1).strip(), chunk.page_number)
        ordered = sorted(headings)
        for chunk in passages:
            start = (chunk.page_number, getattr(chunk, "block_index", 0), chunk.start_char)
            before = [pos for pos in ordered if pos <= start]
            if before:
                title, page = headings[before[-1]]
                # Carry context only to the same or immediately following page.
                if chunk.page_number - page <= 1:
                    context[str(chunk.chunk_id)] = {"heading": title, "heading_page": page}
    return context
