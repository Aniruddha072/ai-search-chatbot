"""Default Ranker implementation: a weighted heuristic, not an embedding
reranker. See docs/decisions.md, Decision 1.4 - this is a deliberate
MVP choice, kept behind the Ranker port so it can be swapped for a
semantic reranker later without touching anything that calls it.
"""
import re
from datetime import date, datetime

from src.domain.entities import SearchResult
from src.domain.interfaces import Ranker

DEFAULT_PROVIDER_WEIGHT = 0.5
DEFAULT_KEYWORD_WEIGHT = 0.35
DEFAULT_RECENCY_WEIGHT = 0.15

_NEUTRAL_RECENCY_SCORE = 0.5
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class HeuristicRanker(Ranker):
    def __init__(
        self,
        provider_weight: float = DEFAULT_PROVIDER_WEIGHT,
        keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
        recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    ) -> None:
        self._provider_weight = provider_weight
        self._keyword_weight = keyword_weight
        self._recency_weight = recency_weight

    def rank(self, results: list[SearchResult], original_query: str) -> list[SearchResult]:
        return sorted(results, key=lambda r: self._score(r, original_query), reverse=True)

    def _score(self, result: SearchResult, original_query: str) -> float:
        provider_score = result.provider_score if result.provider_score is not None else 0.0
        keyword_score = self._keyword_overlap(result, original_query)
        recency_score = self._recency_score(result)
        return (
            self._provider_weight * provider_score
            + self._keyword_weight * keyword_score
            + self._recency_weight * recency_score
        )

    @staticmethod
    def _keyword_overlap(result: SearchResult, original_query: str) -> float:
        query_terms = _tokenize(original_query)
        if not query_terms:
            return 0.0
        result_terms = _tokenize(f"{result.title} {result.snippet}")
        return len(query_terms & result_terms) / len(query_terms)

    @staticmethod
    def _recency_score(result: SearchResult) -> float:
        if not result.published_date:
            return _NEUTRAL_RECENCY_SCORE
        try:
            published = datetime.fromisoformat(result.published_date).date()
        except ValueError:
            return _NEUTRAL_RECENCY_SCORE
        days_old = (date.today() - published).days
        if days_old < 0:
            return 1.0
        return 1.0 / (1.0 + days_old / 365)
