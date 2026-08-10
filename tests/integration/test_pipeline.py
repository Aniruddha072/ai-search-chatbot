"""Real end-to-end run through the actual built pipeline: Tavily search,
Groq query planning, Groq answer generation - everything. Skipped by
default - opt in with RUN_INTEGRATION_TESTS=1. This is the roadmap's
"manual end-to-end smoke test with a real question," made automated and
repeatable instead of a one-off script.
"""
import os

import pytest

from src.bootstrap import build_chat_pipeline

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="set RUN_INTEGRATION_TESTS=1 to run tests that call real Tavily/Groq APIs",
)


@pytest.mark.asyncio
async def test_real_pipeline_produces_a_grounded_answer():
    pipeline = build_chat_pipeline()

    answer = await pipeline.handle("What are the best computer engineering colleges in Pune?")

    assert answer.text
    assert len(answer.sources) >= 1
    for source in answer.sources:
        assert source.url.startswith("http")


@pytest.mark.asyncio
async def test_real_pipeline_streams_a_grounded_answer():
    pipeline = build_chat_pipeline()

    stream = await pipeline.handle_streaming(
        "What are the best computer engineering colleges in Pune?"
    )
    chunks = [chunk async for chunk in stream]
    answer = await stream.get_answer()

    assert len(chunks) > 1
    assert answer.text == "".join(chunks)
    assert len(answer.sources) >= 1
    assert answer.evaluation is not None
