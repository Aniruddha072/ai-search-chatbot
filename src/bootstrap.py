"""Composition root: the one place in the codebase that constructs
concrete infrastructure classes and wires them into a ChatPipeline.
Everywhere else depends on abstractions or receives already-built
instances via constructor injection.

Plain functions, no @lru_cache (unlike get_settings()): each has exactly
one natural call site per process - the caller holds the single
ChatPipeline instance, so there's nothing to memoize here.

Two public entry points share everything except the evaluator:
build_chat_pipeline() (the CLI - real RagasEvaluator, unchanged since
Phase 8) and build_demo_pipeline() (Phase 14's public Streamlit demo -
NullEvaluator, so it never makes the extra Groq calls RAGAS needs on a
public-facing surface with free-tier quota; see docs/decisions.md,
14.x). An optional/defaulted evaluator parameter on one function was
considered and rejected - it would contradict Decision 9.2's precedent
of explicit required collaborators over implicit defaults, and would
let a future caller silently get real RAGAS scores (or silently not)
depending on an easy-to-miss default rather than which function they
called.
"""
from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.evaluation_service import EvaluationService
from src.application.pipeline import ChatPipeline
from src.application.query_planner import QueryPlanner
from src.application.ranker import HeuristicRanker
from src.application.search_orchestrator import SearchOrchestrator
from src.config.settings import Settings, get_settings
from src.domain.interfaces import Evaluator
from src.infrastructure.cache.memory_cache import InMemoryCache
from src.infrastructure.content.content_extractor import TrafilaturaContentExtractor
from src.infrastructure.evaluation.null_evaluator import NullEvaluator
from src.infrastructure.llm.groq_client import GroqClient
from src.infrastructure.search.tavily_provider import TavilyProvider


def _build_pipeline(settings: Settings, evaluator: Evaluator) -> ChatPipeline:
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

    evaluation_service = EvaluationService(
        evaluator=evaluator,
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


def build_chat_pipeline() -> ChatPipeline:
    # Imported here, not at module level: ragas_evaluator.py imports ragas,
    # which the demo's requirements.txt deliberately excludes (Decision
    # 8.1's install-time cost, now also a demo-bundle-size concern). A
    # module-level import would make importing bootstrap.py itself require
    # ragas, breaking build_demo_pipeline() on Streamlit Cloud even though
    # it never touches RagasEvaluator.
    from src.infrastructure.evaluation.ragas_evaluator import RagasEvaluator

    settings = get_settings()
    # RagasEvaluator gets its own instructor-wrapped Groq client rather than
    # reusing _build_pipeline's groq_client - it goes through instructor's
    # own client construction (instructor.from_provider), not
    # GroqClient/AsyncGroq directly, so there's no shared instance to reuse.
    evaluator = RagasEvaluator(
        api_key=settings.groq_api_key, model=settings.groq_capable_model
    )
    return _build_pipeline(settings, evaluator)


def build_demo_pipeline() -> ChatPipeline:
    settings = get_settings()
    return _build_pipeline(settings, NullEvaluator())
