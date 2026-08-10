import httpx
import pytest
from tavily.errors import BadRequestError
from tavily.errors import TimeoutError as TavilyTimeoutError

from src.domain.exceptions import SearchProviderError
from src.infrastructure.search.tavily_provider import TavilyProvider

TAVILY_RESPONSE = {
    "query": "best computer engineering colleges in pune",
    "results": [
        {
            "url": "https://www.pccoepune.com",
            "title": "PCCOE - Top Autonomous Engineering College Pune",
            "content": "PCCOE, Pune is the best Computer engineering college.",
            "score": 0.92,
            "raw_content": None,
            "id": "858d05-00",
        },
        {
            "url": "https://collegedunia.com/btech/computer-science/pune-colleges",
            "title": "Top BE/B.Tech in Computer Science Colleges in Pune",
            "content": "Ranking #1 COEP Technological University #2 VIT Pune.",
            "score": 0.87,
            "raw_content": None,
            "id": "12ab34-01",
        },
    ],
}


class FakeAsyncTavilyClient:
    """Stands in for tavily.AsyncTavilyClient - records the call it
    received and returns a canned, real-shaped response.
    """

    def __init__(self) -> None:
        self.received_kwargs: dict | None = None

    async def search(self, **kwargs) -> dict:
        self.received_kwargs = kwargs
        return TAVILY_RESPONSE


@pytest.mark.asyncio
async def test_search_maps_tavily_fields_to_search_result():
    provider = TavilyProvider(api_key="test-key")
    fake_client = FakeAsyncTavilyClient()
    provider._client = fake_client

    results = await provider.search("best computer engineering colleges in pune", max_results=2)

    assert len(results) == 2
    first = results[0]
    assert first.url == "https://www.pccoepune.com"
    assert first.title == "PCCOE - Top Autonomous Engineering College Pune"
    assert first.snippet == "PCCOE, Pune is the best Computer engineering college."
    assert first.provider_score == 0.92
    assert first.source_query == "best computer engineering colleges in pune"


@pytest.mark.asyncio
async def test_search_defaults_missing_published_date_to_none():
    provider = TavilyProvider(api_key="test-key")
    provider._client = FakeAsyncTavilyClient()

    results = await provider.search("some query", max_results=2)

    assert all(r.published_date is None for r in results)


@pytest.mark.asyncio
async def test_search_passes_query_and_max_results_through():
    provider = TavilyProvider(api_key="test-key")
    fake_client = FakeAsyncTavilyClient()
    provider._client = fake_client

    await provider.search("some query", max_results=3)

    assert fake_client.received_kwargs == {"query": "some query", "max_results": 3}


@pytest.mark.asyncio
async def test_search_filters_out_non_absolute_urls():
    response_with_relative_url = {
        "results": [
            *TAVILY_RESPONSE["results"],
            {
                "url": "/goto?url=CAESdQ",
                "title": "Relative redirect link",
                "content": "should be dropped",
                "score": 0.5,
            },
        ]
    }

    class FakeClient:
        async def search(self, **kwargs):
            return response_with_relative_url

    provider = TavilyProvider(api_key="test-key")
    provider._client = FakeClient()

    results = await provider.search("some query", max_results=3)

    assert len(results) == 2
    assert all(r.url.startswith(("http://", "https://")) for r in results)


class _FlakyThenOkClient:
    """Fails with a retryable error `fail_times` times, then succeeds."""

    def __init__(self, exc: Exception, fail_times: int) -> None:
        self._exc = exc
        self._fail_times = fail_times
        self.call_count = 0

    async def search(self, **kwargs) -> dict:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._exc
        return TAVILY_RESPONSE


class _AlwaysFailsClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.call_count = 0

    async def search(self, **kwargs) -> dict:
        self.call_count += 1
        raise self._exc


@pytest.mark.asyncio
async def test_search_retries_transient_timeout_and_eventually_succeeds():
    provider = TavilyProvider(api_key="test-key", max_retries=3, retry_backoff_seconds=0)
    flaky_client = _FlakyThenOkClient(TavilyTimeoutError(timeout=10.0), fail_times=2)
    provider._client = flaky_client

    results = await provider.search("some query", max_results=2)

    assert len(results) == 2
    assert flaky_client.call_count == 3


@pytest.mark.asyncio
async def test_search_raises_search_provider_error_after_exhausting_retries():
    provider = TavilyProvider(api_key="test-key", max_retries=2, retry_backoff_seconds=0)
    always_fails = _AlwaysFailsClient(TavilyTimeoutError(timeout=10.0))
    provider._client = always_fails

    with pytest.raises(SearchProviderError):
        await provider.search("some query", max_results=2)

    assert always_fails.call_count == 2


@pytest.mark.asyncio
async def test_search_retries_httpx_transport_error():
    provider = TavilyProvider(api_key="test-key", max_retries=3, retry_backoff_seconds=0)
    flaky_client = _FlakyThenOkClient(
        httpx.ConnectError("connection reset"), fail_times=1
    )
    provider._client = flaky_client

    results = await provider.search("some query", max_results=2)

    assert len(results) == 2
    assert flaky_client.call_count == 2


@pytest.mark.asyncio
async def test_search_does_not_retry_non_transient_errors():
    provider = TavilyProvider(api_key="test-key", max_retries=3, retry_backoff_seconds=0)
    always_fails = _AlwaysFailsClient(BadRequestError("bad request"))
    provider._client = always_fails

    with pytest.raises(SearchProviderError):
        await provider.search("some query", max_results=2)

    assert always_fails.call_count == 1
