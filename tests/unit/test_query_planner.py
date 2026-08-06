import asyncio
import json

import pytest

from src.application.query_planner import QueryPlanner
from src.config.prompts.query_planning import QueryPlanResponse
from src.domain.interfaces import LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self, structured_result=None, raise_exc: Exception | None = None, delay: float = 0.0):
        self._structured_result = structured_result
        self._raise_exc = raise_exc
        self._delay = delay

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "unused"

    async def generate_structured(self, prompt, schema, *, system_prompt=None):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raise_exc:
            raise self._raise_exc
        return self._structured_result


@pytest.mark.asyncio
async def test_plan_maps_valid_response_to_query():
    response = QueryPlanResponse(intent="find best CE colleges", complexity="moderate", queries=["q1", "q2"])
    planner = QueryPlanner(FakeLLMProvider(structured_result=response), timeout_seconds=5.0)

    query = await planner.plan("best CE colleges in Pune")

    assert query.original_text == "best CE colleges in Pune"
    assert query.sub_queries == ("q1", "q2")
    assert query.intent == "find best CE colleges"
    assert query.complexity == "moderate"


@pytest.mark.asyncio
async def test_plan_falls_back_on_llm_exception():
    planner = QueryPlanner(FakeLLMProvider(raise_exc=RuntimeError("boom")), timeout_seconds=5.0)

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

    planner = QueryPlanner(MalformedProvider(), timeout_seconds=5.0)

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

    planner = QueryPlanner(TooManyQueriesProvider(), timeout_seconds=5.0)

    query = await planner.plan("what is X?")

    assert query.sub_queries == ("what is X?",)
    assert query.intent == "unknown"


@pytest.mark.asyncio
async def test_plan_falls_back_on_timeout():
    planner = QueryPlanner(FakeLLMProvider(delay=1.0), timeout_seconds=0.05)

    query = await planner.plan("what is X?")

    assert query.sub_queries == ("what is X?",)
