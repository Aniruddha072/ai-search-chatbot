import pytest

from src.domain.entities import EvaluationResult, SearchResult
from src.domain.interfaces import Cache, Evaluator, LLMProvider, Ranker, SearchProvider


@pytest.mark.parametrize(
    "interface", [SearchProvider, LLMProvider, Ranker, Evaluator, Cache]
)
def test_interfaces_cannot_be_instantiated_directly(interface):
    with pytest.raises(TypeError):
        interface()


class DummySearchProvider(SearchProvider):
    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        return [
            SearchResult(
                url="https://example.com",
                title="Example",
                snippet="A snippet",
                source_query=query,
            )
        ]


class IncompleteSearchProvider(SearchProvider):
    """Deliberately missing `search` - should fail at instantiation."""


@pytest.mark.asyncio
async def test_concrete_search_provider_satisfies_interface():
    provider = DummySearchProvider()

    results = await provider.search("some query", max_results=1)

    assert results[0].source_query == "some query"


def test_incomplete_implementation_cannot_be_instantiated():
    with pytest.raises(TypeError):
        IncompleteSearchProvider()


class DummyRanker(Ranker):
    def rank(
        self, results: list[SearchResult], original_query: str
    ) -> list[SearchResult]:
        return sorted(results, key=lambda r: r.title)


def test_concrete_ranker_satisfies_interface():
    ranker = DummyRanker()
    results = [
        SearchResult(url="https://b.com", title="B", snippet="b", source_query="q"),
        SearchResult(url="https://a.com", title="A", snippet="a", source_query="q"),
    ]

    ranked = ranker.rank(results, "q")

    assert [r.title for r in ranked] == ["A", "B"]


class DummyCache(Cache):
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ttl_seconds: int) -> None:
        self._store[key] = value


@pytest.mark.asyncio
async def test_concrete_cache_round_trips_a_value():
    cache = DummyCache()

    await cache.set("k", "v", ttl_seconds=60)
    result = await cache.get("k")

    assert result == "v"


class DummyEvaluator(Evaluator):
    async def evaluate(
        self, question: str, answer: str, contexts: list[str]
    ) -> EvaluationResult:
        return EvaluationResult(faithfulness=1.0)


@pytest.mark.asyncio
async def test_concrete_evaluator_returns_evaluation_result():
    evaluator = DummyEvaluator()

    result = await evaluator.evaluate("q", "a", ["ctx"])

    assert result.faithfulness == 1.0
