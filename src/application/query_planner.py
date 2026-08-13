"""Turns a raw user question into a validated Query entity via Groq.

Any failure - a timeout, a network error, or the LLM producing JSON that
doesn't satisfy QueryPlanResponse's schema (including more than 5 queries,
rejected at the schema layer before Query.__post_init__ ever sees it) -
falls back to a single-query Query built from the raw question, rather
than propagating the failure to the rest of the pipeline.

Successful plans are cached by normalized question text (Phase 9) - the
fallback Query is deliberately never cached, so a transient LLM failure
can't poison future identical requests with a degraded plan.

Phase 15 adds an optional `conversation` parameter to plan() so a
follow-up question ("which one is cheapest?") can be resolved against a
few recent turns instead of being planned in isolation. Reference
resolution is folded into this same Groq call rather than a separate
rewrite call - it's the same kind of work this method already does
(deciding what the user actually wants before turning it into search
queries), and a second call would double the Groq round-trips on every
follow-up turn. `conversation` defaults to None everywhere, so any
existing caller that doesn't pass one gets byte-identical prompts and
cache keys to before this phase.
"""
import asyncio
import hashlib

from src.config.prompts.query_planning import SYSTEM_PROMPT, QueryPlanResponse
from src.domain.entities import ConversationContext, Query
from src.domain.interfaces import Cache, LLMProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _compose_prompt(user_query: str, conversation: ConversationContext | None) -> str:
    if not conversation or not conversation.turns:
        return user_query
    lines = ["Recent conversation:"]
    for turn in conversation.turns:
        lines.append(f"Q: {turn.question}")
        lines.append(f"A: {turn.answer_summary}")
    lines.append(f"Current question: {user_query}")
    return "\n".join(lines)


def _cache_key(user_query: str, conversation: ConversationContext | None) -> str:
    normalized = _normalize(user_query)
    if not conversation or not conversation.turns:
        return normalized
    # The same literal follow-up ("which one is cheapest?") can mean
    # completely different things in two different conversations - folding
    # a digest of the conversation into the key stops one from silently
    # returning a plan cached for the other. Falls back to exactly today's
    # key (normalized text alone) when there's no conversation, so the
    # CLI's existing cache behavior is unaffected.
    history_text = "|".join(
        f"{_normalize(turn.question)}::{_normalize(turn.answer_summary)}"
        for turn in conversation.turns
    )
    digest = hashlib.sha256(history_text.encode("utf-8")).hexdigest()[:16]
    return f"{digest}:{normalized}"


class QueryPlanner:
    def __init__(
        self,
        llm_provider: LLMProvider,
        timeout_seconds: float,
        cache: Cache,
        cache_ttl_seconds: float,
    ) -> None:
        self._llm_provider = llm_provider
        self._timeout_seconds = timeout_seconds
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def plan(
        self, user_query: str, conversation: ConversationContext | None = None
    ) -> Query:
        cache_key = _cache_key(user_query, conversation)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = await asyncio.wait_for(
                self._llm_provider.generate_structured(
                    prompt=_compose_prompt(user_query, conversation),
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

        query = Query(
            original_text=user_query,
            sub_queries=tuple(response.queries),
            intent=response.intent,
            complexity=response.complexity,
        )
        await self._cache.set(cache_key, query, ttl_seconds=self._cache_ttl_seconds)
        return query

    @staticmethod
    def _fallback(user_query: str) -> Query:
        return Query(
            original_text=user_query,
            sub_queries=(user_query,),
            intent="unknown",
            complexity="unknown",
        )
