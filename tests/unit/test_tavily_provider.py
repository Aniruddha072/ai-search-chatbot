import pytest

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
