import asyncio

import pytest

from src.application.context_builder import ContextBuilder
from src.domain.entities import SearchResult
from src.domain.interfaces import ContentExtractor
from src.utils.token_counter import count_tokens


def make_result(url: str, snippet: str, title: str = "Title") -> SearchResult:
    return SearchResult(url=url, title=title, snippet=snippet, source_query="q")


LONG_SNIPPET = " ".join(["word"] * 60)  # 60 words: above the default 40-word thin threshold
SHORT_SNIPPET = "Too short."  # well under 40 words


class FakeContentExtractor(ContentExtractor):
    def __init__(self, by_url: dict[str, str | Exception] | None = None, delay: float = 0.0) -> None:
        self._by_url = by_url or {}
        self._delay = delay
        self.calls: list[str] = []

    async def extract(self, url: str) -> str | None:
        self.calls.append(url)
        if self._delay:
            await asyncio.sleep(self._delay)
        outcome = self._by_url.get(url)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def build_context_builder(
    extractor: ContentExtractor | None = None,
    max_context_sources: int = 6,
    context_token_budget: int = 2500,
    content_fetch_timeout_seconds: float = 5.0,
    full_fetch_candidate_count: int = 3,
    thin_snippet_word_threshold: int = 40,
) -> ContextBuilder:
    return ContextBuilder(
        content_extractor=extractor or FakeContentExtractor(),
        max_context_sources=max_context_sources,
        context_token_budget=context_token_budget,
        content_fetch_timeout_seconds=content_fetch_timeout_seconds,
        full_fetch_candidate_count=full_fetch_candidate_count,
        thin_snippet_word_threshold=thin_snippet_word_threshold,
    )


@pytest.mark.asyncio
async def test_empty_results_returns_empty_tuple():
    sources = await build_context_builder().build([])

    assert sources == ()


@pytest.mark.asyncio
async def test_top_k_selection_drops_results_beyond_max_context_sources():
    results = [make_result(f"https://example.com/{i}", LONG_SNIPPET) for i in range(10)]

    sources = await build_context_builder(max_context_sources=3).build(results)

    assert len(sources) == 3
    assert [s.url for s in sources] == [r.url for r in results[:3]]


@pytest.mark.asyncio
async def test_citation_indices_are_assigned_in_order_starting_at_one():
    results = [make_result(f"https://example.com/{i}", LONG_SNIPPET) for i in range(3)]

    sources = await build_context_builder().build(results)

    assert [s.index for s in sources] == [1, 2, 3]


@pytest.mark.asyncio
async def test_thin_snippet_triggers_full_fetch():
    result = make_result("https://example.com/a", SHORT_SNIPPET)
    extractor = FakeContentExtractor(by_url={"https://example.com/a": "the real full page text"})

    sources = await build_context_builder(extractor=extractor).build([result])

    assert sources[0].content_used == "the real full page text"
    assert extractor.calls == ["https://example.com/a"]


@pytest.mark.asyncio
async def test_long_snippet_does_not_trigger_full_fetch():
    result = make_result("https://example.com/a", LONG_SNIPPET)
    extractor = FakeContentExtractor(by_url={"https://example.com/a": "should never be used"})

    sources = await build_context_builder(extractor=extractor).build([result])

    assert sources[0].content_used == LONG_SNIPPET
    assert extractor.calls == []


@pytest.mark.asyncio
async def test_only_top_full_fetch_candidates_are_eligible():
    results = [make_result(f"https://example.com/{i}", SHORT_SNIPPET) for i in range(5)]
    extractor = FakeContentExtractor()

    await build_context_builder(extractor=extractor, full_fetch_candidate_count=2).build(results)

    assert extractor.calls == ["https://example.com/0", "https://example.com/1"]


@pytest.mark.asyncio
async def test_failed_extraction_falls_back_to_snippet():
    result = make_result("https://example.com/a", SHORT_SNIPPET)
    extractor = FakeContentExtractor(by_url={"https://example.com/a": RuntimeError("boom")})

    sources = await build_context_builder(extractor=extractor).build([result])

    assert sources[0].content_used == SHORT_SNIPPET


@pytest.mark.asyncio
async def test_extraction_returning_none_falls_back_to_snippet():
    result = make_result("https://example.com/a", SHORT_SNIPPET)
    extractor = FakeContentExtractor(by_url={"https://example.com/a": None})

    sources = await build_context_builder(extractor=extractor).build([result])

    assert sources[0].content_used == SHORT_SNIPPET


@pytest.mark.asyncio
async def test_slow_extraction_times_out_and_falls_back_to_snippet():
    result = make_result("https://example.com/a", SHORT_SNIPPET)
    extractor = FakeContentExtractor(by_url={"https://example.com/a": "too slow"}, delay=1.0)

    sources = await build_context_builder(
        extractor=extractor, content_fetch_timeout_seconds=0.05
    ).build([result])

    assert sources[0].content_used == SHORT_SNIPPET


@pytest.mark.asyncio
async def test_token_budget_is_never_exceeded():
    huge_snippet = " ".join(["word"] * 5000)
    results = [make_result(f"https://example.com/{i}", huge_snippet) for i in range(5)]

    sources = await build_context_builder(context_token_budget=1200).build(results)

    total_tokens = sum(count_tokens(s.content_used) for s in sources)
    assert total_tokens <= 1200


@pytest.mark.asyncio
async def test_lower_ranked_sources_dropped_when_budget_exhausted():
    huge_snippet = " ".join(["word"] * 5000)
    results = [make_result(f"https://example.com/{i}", huge_snippet) for i in range(5)]

    sources = await build_context_builder(context_token_budget=1200).build(results)

    assert len(sources) < len(results)
    kept_urls = {s.url for s in sources}
    assert results[0].url in kept_urls


@pytest.mark.asyncio
async def test_higher_ranked_source_gets_full_content_before_lower_ranked_ones():
    small_snippet = " ".join(["word"] * 50)
    results = [
        make_result("https://example.com/first", small_snippet),
        make_result("https://example.com/second", small_snippet),
    ]
    budget = count_tokens(small_snippet) + 5  # enough for the first in full, not much more

    sources = await build_context_builder(context_token_budget=budget).build(results)

    assert sources[0].content_used == small_snippet
