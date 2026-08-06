"""Real network call to Tavily. Skipped by default - opt in with
RUN_INTEGRATION_TESTS=1 so the default `pytest` run stays free, fast,
and offline. This is the only test that would catch Tavily changing
its response shape out from under TavilyProvider's mapping logic.
"""
import os

import pytest
from dotenv import load_dotenv

from src.infrastructure.search.tavily_provider import TavilyProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="set RUN_INTEGRATION_TESTS=1 to run tests that call the real Tavily API",
)


@pytest.mark.asyncio
async def test_real_tavily_search_returns_results():
    # Reads TAVILY_API_KEY directly rather than via get_settings(), which
    # validates the full app config (e.g. GROQ_API_KEY) - unrelated keys
    # not being set yet shouldn't block a Tavily-only integration test.
    load_dotenv()
    provider = TavilyProvider(api_key=os.environ["TAVILY_API_KEY"])

    results = await provider.search(
        "best computer engineering colleges in pune", max_results=3
    )

    assert len(results) > 0
    assert results[0].url.startswith("http")
    assert results[0].title
    assert results[0].snippet
