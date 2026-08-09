"""Real call to Groq. Skipped by default - opt in with
RUN_INTEGRATION_TESTS=1, matching the Tavily integration test's pattern.
"""
import os

import pytest
from dotenv import load_dotenv

from src.application.query_planner import QueryPlanner
from src.infrastructure.cache.memory_cache import InMemoryCache
from src.infrastructure.llm.groq_client import GroqClient

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="set RUN_INTEGRATION_TESTS=1 to run tests that call the real Groq API",
)


@pytest.mark.asyncio
async def test_real_query_planner_produces_a_valid_query():
    # Reads GROQ_API_KEY directly rather than via get_settings(), same
    # reasoning as the Tavily integration test (Decision 2.4): this test
    # shouldn't fail because an unrelated required setting is missing.
    load_dotenv()
    llm = GroqClient(
        api_key=os.environ["GROQ_API_KEY"],
        fast_model="llama-3.1-8b-instant",
        capable_model="llama-3.3-70b-versatile",
    )
    planner = QueryPlanner(llm, timeout_seconds=15.0, cache=InMemoryCache(), cache_ttl_seconds=60)

    query = await planner.plan("What are the best computer engineering colleges in Pune?")

    assert 1 <= len(query.sub_queries) <= 5
    assert query.intent != "unknown"
