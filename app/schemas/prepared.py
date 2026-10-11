"""Prepared content retains the parsed document's structure and source rules."""

from typing import Literal

from app.schemas.documents import ParsedDocument


class PreparedDocument(ParsedDocument):
    """A separate, conservatively cleaned copy; it is not a collection of chunks."""

    preparation_version: Literal[1] = 1
