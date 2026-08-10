"""Real call to Groq. Skipped by default - opt in with
RUN_INTEGRATION_TESTS=1, matching the Tavily/query-planner integration
tests' pattern.
"""
import os

import pytest
from dotenv import load_dotenv

from src.application.answer_generator import AnswerGenerator
from src.domain.entities import Query, Source
from src.infrastructure.llm.groq_client import GroqClient

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="set RUN_INTEGRATION_TESTS=1 to run tests that call the real Groq API",
)


@pytest.mark.asyncio
async def test_real_answer_generator_produces_a_grounded_cited_answer():
    load_dotenv()
    llm = GroqClient(
        api_key=os.environ["GROQ_API_KEY"],
        fast_model="llama-3.1-8b-instant",
        capable_model="llama-3.3-70b-versatile",
    )
    generator = AnswerGenerator(llm, timeout_seconds=15.0)
    query = Query(
        original_text="What are good computer engineering colleges in Pune?",
        sub_queries=("computer engineering colleges Pune",),
        intent="find colleges",
        complexity="simple",
    )
    sources = (
        Source(
            index=1,
            url="https://example.com/pccoe",
            title="PCCOE Admissions",
            content_used="PCCOE, Pune offers a well-regarded Computer Engineering program with modern labs.",
        ),
        Source(
            index=2,
            url="https://example.com/weather",
            title="Pune Weather Today",
            content_used="Expect sunny skies in Pune today with a high of 30C.",
        ),
    )

    answer = await generator.generate(query, sources)

    assert answer.text
    assert len(answer.sources) >= 1
    assert all(s.index in (1, 2) for s in answer.sources)


@pytest.mark.asyncio
async def test_real_answer_generator_streams_and_matches_build_answer():
    load_dotenv()
    llm = GroqClient(
        api_key=os.environ["GROQ_API_KEY"],
        fast_model="llama-3.1-8b-instant",
        capable_model="llama-3.3-70b-versatile",
    )
    generator = AnswerGenerator(llm, timeout_seconds=15.0)
    query = Query(
        original_text="What are good computer engineering colleges in Pune?",
        sub_queries=("computer engineering colleges Pune",),
        intent="find colleges",
        complexity="simple",
    )
    sources = (
        Source(
            index=1,
            url="https://example.com/pccoe",
            title="PCCOE Admissions",
            content_used="PCCOE, Pune offers a well-regarded Computer Engineering program with modern labs.",
        ),
    )

    stream = generator.generate_streaming(query, sources)
    chunks = [chunk async for chunk in stream]
    answer = stream.build_answer()

    assert len(chunks) > 1  # a real streamed response arrives in more than one piece
    assert answer.text == "".join(chunks)
    assert len(answer.sources) >= 1
