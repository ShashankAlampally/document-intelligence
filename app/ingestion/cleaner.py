"""Conservative whitespace normalization without rewriting document meaning."""

import re


def clean_text(text: str) -> str:
    """Normalize line endings and spaces, keeping lines and paragraph boundaries.

    Repeated blank lines become one blank line. Case, punctuation, numbers,
    labels, and ordering remain unchanged. No joining of wrapped words or emails.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def clean_optional_text(text: str | None) -> str | None:
    """Represent absent or whitespace-only optional content as None."""
    return clean_text(text) or None if text is not None else None
