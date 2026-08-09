import asyncio
import json

import pytest

from src.application.query_planner import QueryPlanner
from src.config.prompts.query_planning import QueryPlanResponse
from src.domain.interfaces import Cache, LLMProvider
from src.infrastructure.cache.memory_cache import InMemoryCache


class FakeLLMProvider(LLMProvider):
    def __init__(self, structured_result=None, raise_exc: Exception | None = None, delay: float = 0.0):
        self._structured_result = structured_result
        self._raise_exc = raise_exc
        self._delay = delay
        self.call_count = 0

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "unused"

    async def generate_structured(self, prompt, schema, *, system_prompt=None):
        self.call_count += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raise_exc:
            raise self._raise_exc
        return self._structured_result


def make_planner(llm_provider: LLMProvider, cache: Cache | None = None, timeout_seconds: float = 5.0) -> QueryPlanner:
    return QueryPlanner(
        llm_provider,
        timeout_seconds=timeout_seconds,
        cache=cache or InMemoryCache(),
        cache_ttl_seconds=60,
    )


@pytest.mark.asyncio
async def test_plan_maps_valid_response_to_query():
    response = QueryPlanResponse(intent="find best CE colleges", complexity="moderate", queries=["q1", "q2"])
    planner = make_planner(FakeLLMProvider(structured_result=response))

    query = await planner.plan("best CE colleges in Pune")

    assert query.original_text == "best CE colleges in Pune"
    assert query.sub_queries == ("q1", "q2")
    assert query.intent == "find best CE colleges"
    assert query.complexity == "moderate"


@pytest.mark.asyncio
async def test_plan_falls_back_on_llm_exception():
    planner = make_planner(FakeLLMProvider(raise_exc=RuntimeError("boom")))

    query = await planner.plan("what is X?")

    assert query.original_text == "what is X?"
    assert query.sub_queries == ("what is X?",)
    assert query.intent == "unknown"
    assert query.complexity == "unknown"


@pytest.mark.asyncio
async def test_plan_falls_back_on_malformed_json():
    class MalformedProvider(LLMProvider):
        async def generate(self, prompt, *, system_prompt=None):
            return "unused"

        async def generate_structured(self, prompt, schema, *, system_prompt=None):
            return schema.model_validate_json("not valid json")

    planner = make_planner(MalformedProvider())

    query = await planner.plan("what is X?")

    assert query.sub_queries == ("what is X?",)


@pytest.mark.asyncio
async def test_plan_falls_back_when_schema_rejects_over_five_queries():
    class TooManyQueriesProvider(LLMProvider):
        async def generate(self, prompt, *, system_prompt=None):
            return "unused"

        async def generate_structured(self, prompt, schema, *, system_prompt=None):
            payload = json.dumps(
                {"intent": "x", "complexity": "complex", "queries": ["a", "b", "c", "d", "e", "f"]}
            )
            return schema.model_validate_json(payload)

    planner = make_planner(TooManyQueriesProvider())

    query = await planner.plan("what is X?")

    assert query.sub_queries == ("what is X?",)
    assert query.intent == "unknown"


@pytest.mark.asyncio
async def test_plan_falls_back_on_timeout():
    planner = make_planner(FakeLLMProvider(delay=1.0), timeout_seconds=0.05)

    query = await planner.plan("what is X?")

    assert query.sub_queries == ("what is X?",)


@pytest.mark.asyncio
async def test_repeated_identical_question_hits_the_cache_and_skips_the_llm():
    response = QueryPlanResponse(intent="find best CE colleges", complexity="moderate", queries=["q1"])
    llm_provider = FakeLLMProvider(structured_result=response)
    planner = make_planner(llm_provider)

    first = await planner.plan("best CE colleges in Pune")
    second = await planner.plan("best CE colleges in Pune")

    assert llm_provider.call_count == 1
    assert second == first


@pytest.mark.asyncio
async def test_cache_key_is_normalized_case_and_whitespace_insensitive():
    response = QueryPlanResponse(intent="find best CE colleges", complexity="moderate", queries=["q1"])
    llm_provider = FakeLLMProvider(structured_result=response)
    planner = make_planner(llm_provider)

    await planner.plan("Best CE Colleges in Pune")
    await planner.plan("  best   ce colleges   in pune  ")

    assert llm_provider.call_count == 1


@pytest.mark.asyncio
async def test_fallback_plans_are_not_cached():
    llm_provider = FakeLLMProvider(raise_exc=RuntimeError("boom"))
    planner = make_planner(llm_provider)

    await planner.plan("what is X?")
    await planner.plan("what is X?")

    # No caching of the fallback path means the LLM is retried every time,
    # not silently stuck returning a degraded plan forever.
    assert llm_provider.call_count == 2
