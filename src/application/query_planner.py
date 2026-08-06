"""Turns a raw user question into a validated Query entity via Groq.

Any failure - a timeout, a network error, or the LLM producing JSON that
doesn't satisfy QueryPlanResponse's schema (including more than 5 queries,
rejected at the schema layer before Query.__post_init__ ever sees it) -
falls back to a single-query Query built from the raw question, rather
than propagating the failure to the rest of the pipeline.
"""
import asyncio

from src.config.prompts.query_planning import SYSTEM_PROMPT, QueryPlanResponse
from src.domain.entities import Query
from src.domain.interfaces import LLMProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueryPlanner:
    def __init__(self, llm_provider: LLMProvider, timeout_seconds: float) -> None:
        self._llm_provider = llm_provider
        self._timeout_seconds = timeout_seconds

    async def plan(self, user_query: str) -> Query:
        try:
            response = await asyncio.wait_for(
                self._llm_provider.generate_structured(
                    prompt=user_query,
                    schema=QueryPlanResponse,
                    system_prompt=SYSTEM_PROMPT,
                ),
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            logger.warning(
                "query planning failed, falling back to single query: %s", exc
            )
            return self._fallback(user_query)

        return Query(
            original_text=user_query,
            sub_queries=tuple(response.queries),
            intent=response.intent,
            complexity=response.complexity,
        )

    @staticmethod
    def _fallback(user_query: str) -> Query:
        return Query(
            original_text=user_query,
            sub_queries=(user_query,),
            intent="unknown",
            complexity="unknown",
        )
