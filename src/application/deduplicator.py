"""Removes duplicate search results before ranking.

Two passes: exact-URL (after normalization) and near-duplicate content
(title+snippet similarity). No interface - unlike SearchProvider or
Ranker, there's no second implementation of "how to deduplicate" this
project plans to swap in later, so this stays a concrete class rather
than a port.
"""
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

from src.domain.entities import SearchResult

DEFAULT_SIMILARITY_THRESHOLD = 0.85


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


class Deduplicator:
    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> None:
        self._similarity_threshold = similarity_threshold

    def deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        by_url = self._dedupe_by_url(results)
        return self._dedupe_by_content_similarity(by_url)

    def _dedupe_by_url(self, results: list[SearchResult]) -> list[SearchResult]:
        seen: set[str] = set()
        kept: list[SearchResult] = []
        for result in results:
            normalized = _normalize_url(result.url)
            if normalized in seen:
                continue
            seen.add(normalized)
            kept.append(result)
        return kept

    def _dedupe_by_content_similarity(self, results: list[SearchResult]) -> list[SearchResult]:
        kept: list[SearchResult] = []
        for result in results:
            text = f"{result.title} {result.snippet}"
            if any(
                self._similarity(text, f"{k.title} {k.snippet}") >= self._similarity_threshold
                for k in kept
            ):
                continue
            kept.append(result)
        return kept

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()
