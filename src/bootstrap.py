"""Composition root: the one place in the codebase that constructs
concrete infrastructure classes and wires them into a ChatPipeline.
Everywhere else depends on abstractions or receives already-built
instances via constructor injection.

Plain function, no @lru_cache (unlike get_settings()): this has exactly
one natural call site per process - the caller holds the single
ChatPipeline instance, so there's nothing to memoize here.
"""
from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.evaluation_service import EvaluationService
from src.application.pipeline import ChatPipeline
from src.application.query_planner import QueryPlanner
from src.application.ranker import HeuristicRanker
from src.application.search_orchestrator import SearchOrchestrator
from src.config.settings import get_settings
from src.infrastructure.cache.memory_cache import InMemoryCache
from src.infrastructure.content.content_extractor import TrafilaturaContentExtractor
from src.infrastructure.evaluation.ragas_evaluator import RagasEvaluator
from src.infrastructure.llm.groq_client import GroqClient
from src.infrastructure.search.tavily_provider import TavilyProvider


def build_chat_pipeline() -> ChatPipeline:
    settings = get_settings()

    # Two separate cache instances, not one shared one - a raw user question
    # could in principle collide with a generated sub-query string, and a
    # shared cache would then return the wrong *type* of cached value.
    query_plan_cache = InMemoryCache()
    search_result_cache = InMemoryCache()

    search_orchestrator = SearchOrchestrator(
        provider=TavilyProvider(
            api_key=settings.tavily_api_key,
            max_retries=settings.max_retry_attempts,
            retry_backoff_seconds=settings.retry_backoff_seconds,
        ),
        timeout_seconds=settings.search_timeout_seconds,
        cache=search_result_cache,
        cache_ttl_seconds=settings.search_result_cache_ttl_seconds,
    )
    context_builder = ContextBuilder(
        content_extractor=TrafilaturaContentExtractor(),
        max_context_sources=settings.max_context_sources,
        context_token_budget=settings.context_token_budget,
        content_fetch_timeout_seconds=settings.content_fetch_timeout_seconds,
    )

    # One GroqClient instance shared between QueryPlanner and AnswerGenerator -
    # this *is* the "reused async HTTP clients" optimization from decisions.md,
    # achieved by correct wiring here rather than extra code anywhere else.
    groq_client = GroqClient(
        api_key=settings.groq_api_key,
        fast_model=settings.groq_fast_model,
        capable_model=settings.groq_capable_model,
        max_retries=settings.max_retry_attempts,
        retry_backoff_seconds=settings.retry_backoff_seconds,
    )

    # RagasEvaluator gets its own instructor-wrapped Groq client rather than
    # reusing `groq_client` above - it goes through instructor's own client
    # construction (instructor.from_provider), not GroqClient/AsyncGroq
    # directly, so there's no shared instance to reuse here.
    evaluation_service = EvaluationService(
        evaluator=RagasEvaluator(
            api_key=settings.groq_api_key, model=settings.groq_capable_model
        ),
        timeout_seconds=settings.evaluation_timeout_seconds,
    )

    return ChatPipeline(
        query_planner=QueryPlanner(
            groq_client,
            timeout_seconds=settings.llm_timeout_seconds,
            cache=query_plan_cache,
            cache_ttl_seconds=settings.query_plan_cache_ttl_seconds,
        ),
        search_orchestrator=search_orchestrator,
        deduplicator=Deduplicator(),
        ranker=HeuristicRanker(),
        context_builder=context_builder,
        answer_generator=AnswerGenerator(groq_client, timeout_seconds=settings.llm_timeout_seconds),
        evaluation_service=evaluation_service,
        max_results_per_query=settings.max_search_results,
        max_query_length=settings.max_query_length,
    )
