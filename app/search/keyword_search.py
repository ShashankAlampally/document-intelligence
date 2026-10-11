"""BM25 over saved text, with a bounded cache rebuilt when the corpus changes."""

import hashlib
import re
from collections import OrderedDict

from rank_bm25 import BM25Plus

from app.schemas.search import SearchHit

STOP_WORDS = set(
    "a an and are as at be by for from how in is it of on or that the their "
    "this to what when where which who with must".split()
)


def tokenize(text: str) -> list[str]:
    return [
        word for word in re.findall(r"[\w]+(?:-[\w]+)*", text.lower()) if word not in STOP_WORDS
    ]


class KeywordSearch:
    def __init__(self):
        self.cache = OrderedDict()

    def search(self, query, chunks, top_k):
        chunks = sorted(chunks, key=lambda chunk: str(chunk.chunk_id))
        query_tokens = tokenize(query)
        if not chunks or not query_tokens:
            return []
        corpus = [tokenize(chunk.text) for chunk in chunks]
        if not any(corpus):
            return []
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(str(chunk.chunk_id).encode())
            digest.update(chunk.text.encode())
            digest.update(b"\x00")
        key = digest.hexdigest()
        if key not in self.cache:
            self.cache[key] = BM25Plus(corpus)
            if len(self.cache) > 8:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        scores = self.cache[key].get_scores(query_tokens)
        matches = [
            index for index, words in enumerate(corpus) if set(words).intersection(query_tokens)
        ]
        matches.sort(key=lambda index: (-scores[index], str(chunks[index].chunk_id)))
        return [
            SearchHit(chunk=chunks[index], keyword_score=float(scores[index]))
            for index in matches[:top_k]
        ]
