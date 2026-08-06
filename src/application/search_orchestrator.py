"""Runs a Query's sub-queries concurrently against one SearchProvider.

Pure mechanism, not policy: best-effort concurrent fetch with a per-query
timeout. A failed or timed-out sub-query is logged and dropped - even if
every sub-query fails, this returns an empty list rather than raising.
Deciding what "no results" should mean to the user is a pipeline-level
concern (see docs/decisions.md, Error Handling Strategy), not this class's.
"""
import asyncio

from src.domain.entities import Query, SearchResult
from src.domain.interfaces import SearchProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SearchOrchestrator:
    def __init__(self, provider: SearchProvider, timeout_seconds: float) -> None:
        self._provider = provider
        self._timeout_seconds = timeout_seconds

    async def _search_one(self, sub_query: str, max_results: int) -> list[SearchResult]:
        return await asyncio.wait_for(
            self._provider.search(sub_query, max_results),
            timeout=self._timeout_seconds,
        )

    async def search_all(self, query: Query, max_results_per_query: int) -> list[SearchResult]:
        tasks = [
            self._search_one(sub_query, max_results_per_query)
            for sub_query in query.sub_queries
        ]
        results_or_errors = await asyncio.gather(*tasks, return_exceptions=True)

        combined: list[SearchResult] = []
        for sub_query, result in zip(query.sub_queries, results_or_errors):
            if isinstance(result, Exception):
                logger.warning("sub-query failed, skipping: %r (%s)", sub_query, result)
                continue
            combined.extend(result)

        return combined
