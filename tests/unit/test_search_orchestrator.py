import asyncio

import pytest

from src.application.search_orchestrator import SearchOrchestrator
from src.domain.entities import Query, SearchResult
from src.domain.interfaces import Cache, SearchProvider
from src.infrastructure.cache.memory_cache import InMemoryCache


def make_query(*sub_queries: str) -> Query:
    return Query(
        original_text="original question",
        sub_queries=sub_queries,
        intent="comparison",
        complexity="high",
    )


def make_orchestrator(
    provider: SearchProvider, cache: Cache | None = None, timeout_seconds: float = 5.0
) -> SearchOrchestrator:
    return SearchOrchestrator(
        provider=provider,
        timeout_seconds=timeout_seconds,
        cache=cache or InMemoryCache(),
        cache_ttl_seconds=60,
    )


class FailingOnQueryProvider(SearchProvider):
    """Raises for one specific sub-query, succeeds for the rest."""

    def __init__(self, failing_query: str) -> None:
        self._failing_query = failing_query

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if query == self._failing_query:
            raise RuntimeError("provider exploded")
        return [
            SearchResult(url=f"https://example.com/{query}", title=query, snippet="ok", source_query=query)
        ]


class SlowProvider(SearchProvider):
    """Never resolves for one query, so the orchestrator's timeout must fire."""

    def __init__(self, slow_query: str, delay_seconds: float) -> None:
        self._slow_query = slow_query
        self._delay_seconds = delay_seconds

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if query == self._slow_query:
            await asyncio.sleep(self._delay_seconds)
        return [
            SearchResult(url=f"https://example.com/{query}", title=query, snippet="ok", source_query=query)
        ]


class CountingProvider(SearchProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        self.calls.append((query, max_results))
        return [
            SearchResult(url=f"https://example.com/{query}", title=query, snippet="ok", source_query=query)
        ]


@pytest.mark.asyncio
async def test_partial_failure_returns_results_from_successful_queries():
    query = make_query("query one", "query two", "query three")
    provider = FailingOnQueryProvider(failing_query="query two")
    orchestrator = make_orchestrator(provider)

    results = await orchestrator.search_all(query, max_results_per_query=5)

    returned_queries = {r.source_query for r in results}
    assert returned_queries == {"query one", "query three"}


@pytest.mark.asyncio
async def test_all_queries_failing_returns_empty_list_without_raising():
    query = make_query("query one")
    provider = FailingOnQueryProvider(failing_query="query one")
    orchestrator = make_orchestrator(provider)

    results = await orchestrator.search_all(query, max_results_per_query=5)

    assert results == []


@pytest.mark.asyncio
async def test_slow_query_is_dropped_after_timeout():
    query = make_query("fast query", "slow query")
    provider = SlowProvider(slow_query="slow query", delay_seconds=1.0)
    orchestrator = make_orchestrator(provider, timeout_seconds=0.05)

    results = await orchestrator.search_all(query, max_results_per_query=5)

    returned_queries = {r.source_query for r in results}
    assert returned_queries == {"fast query"}


@pytest.mark.asyncio
async def test_queries_run_concurrently_not_sequentially():
    query = make_query("a", "b", "c")

    # every query takes ~0.2s; if total elapsed stays near 0.2s (not 0.6s),
    # they ran concurrently rather than one after another.
    class UniformDelayProvider(SearchProvider):
        async def search(self, query: str, max_results: int) -> list[SearchResult]:
            await asyncio.sleep(0.2)
            return [SearchResult(url="https://example.com", title=query, snippet="ok", source_query=query)]

    orchestrator = make_orchestrator(UniformDelayProvider())

    start = asyncio.get_event_loop().time()
    results = await orchestrator.search_all(query, max_results_per_query=5)
    elapsed = asyncio.get_event_loop().time() - start

    assert len(results) == 3
    assert elapsed < 0.4


@pytest.mark.asyncio
async def test_repeated_sub_query_hits_the_cache_and_skips_the_provider():
    query = make_query("best CE colleges in Pune")
    provider = CountingProvider()
    orchestrator = make_orchestrator(provider)

    await orchestrator.search_all(query, max_results_per_query=5)
    await orchestrator.search_all(query, max_results_per_query=5)

    assert provider.calls == [("best CE colleges in Pune", 5)]


@pytest.mark.asyncio
async def test_different_max_results_does_not_wrongly_hit_the_cache():
    query = make_query("best CE colleges in Pune")
    provider = CountingProvider()
    orchestrator = make_orchestrator(provider)

    await orchestrator.search_all(query, max_results_per_query=3)
    await orchestrator.search_all(query, max_results_per_query=5)

    assert provider.calls == [("best CE colleges in Pune", 3), ("best CE colleges in Pune", 5)]


@pytest.mark.asyncio
async def test_cache_key_is_normalized_case_and_whitespace_insensitive():
    provider = CountingProvider()
    orchestrator = make_orchestrator(provider)

    await orchestrator.search_all(make_query("Best CE Colleges"), max_results_per_query=5)
    await orchestrator.search_all(make_query("  best   ce colleges  "), max_results_per_query=5)

    assert len(provider.calls) == 1
