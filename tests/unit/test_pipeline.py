"""ChatPipeline tested with the real SearchOrchestrator, Deduplicator,
HeuristicRanker, ContextBuilder, QueryPlanner, AnswerGenerator, and
EvaluationService - faked only at the true I/O boundary (SearchProvider,
LLMProvider, ContentExtractor, Evaluator). Exercises the entire real
chain offline.
"""
import pytest

from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.evaluation_service import EvaluationService
from src.application.pipeline import ChatPipeline
from src.application.query_planner import QueryPlanner
from src.application.ranker import HeuristicRanker
from src.application.search_orchestrator import SearchOrchestrator
from src.config.prompts.query_planning import QueryPlanResponse
from src.domain.entities import EvaluationResult, SearchResult
from src.domain.interfaces import ContentExtractor, Evaluator, LLMProvider, SearchProvider
from src.infrastructure.cache.memory_cache import InMemoryCache


class FakeSearchProvider(SearchProvider):
    def __init__(self, results_by_query: dict[str, list[SearchResult]] | None = None):
        self._results_by_query = results_by_query or {}

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        return self._results_by_query.get(query, [])


class FakeContentExtractor(ContentExtractor):
    async def extract(self, url: str) -> str | None:
        return None  # always fall back to the snippet


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        structured_response: QueryPlanResponse | None = None,
        raise_on_structured: Exception | None = None,
        generate_response: str | None = None,
    ):
        self._structured_response = structured_response
        self._raise_on_structured = raise_on_structured
        self._generate_response = generate_response

    async def generate_structured(self, prompt, schema, *, system_prompt=None):
        if self._raise_on_structured:
            raise self._raise_on_structured
        return self._structured_response

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return self._generate_response


class FakeEvaluator(Evaluator):
    def __init__(
        self, result: EvaluationResult | None = None, raise_exc: Exception | None = None
    ):
        self._result = result or EvaluationResult(faithfulness=0.9, context_precision=0.9)
        self._raise_exc = raise_exc

    async def evaluate(self, question: str, answer: str, contexts: list[str]) -> EvaluationResult:
        if self._raise_exc:
            raise self._raise_exc
        return self._result


def build_pipeline(
    search_provider: SearchProvider,
    llm_provider: LLMProvider,
    evaluator: Evaluator | None = None,
) -> ChatPipeline:
    return ChatPipeline(
        query_planner=QueryPlanner(
            llm_provider, timeout_seconds=5.0, cache=InMemoryCache(), cache_ttl_seconds=60
        ),
        search_orchestrator=SearchOrchestrator(
            search_provider, timeout_seconds=5.0, cache=InMemoryCache(), cache_ttl_seconds=60
        ),
        deduplicator=Deduplicator(),
        ranker=HeuristicRanker(),
        context_builder=ContextBuilder(
            content_extractor=FakeContentExtractor(),
            max_context_sources=5,
            context_token_budget=2500,
            content_fetch_timeout_seconds=5.0,
        ),
        answer_generator=AnswerGenerator(llm_provider, timeout_seconds=5.0),
        evaluation_service=EvaluationService(evaluator or FakeEvaluator(), timeout_seconds=5.0),
        max_results_per_query=5,
        max_query_length=500,
    )


@pytest.mark.asyncio
async def test_full_pipeline_produces_a_grounded_cited_answer():
    sub_query = "best computer engineering colleges pune"
    search_provider = FakeSearchProvider(
        {
            sub_query: [
                SearchResult(
                    url="https://example.com/pccoe",
                    title="PCCOE Admissions",
                    snippet="PCCOE, Pune offers a well-regarded Computer Engineering program with modern labs.",
                    source_query=sub_query,
                    provider_score=0.9,
                )
            ]
        }
    )
    llm_provider = FakeLLMProvider(
        structured_response=QueryPlanResponse(
            intent="find CE colleges", complexity="simple", queries=[sub_query]
        ),
        generate_response="PCCOE is a great choice [1].",
    )
    pipeline = build_pipeline(search_provider, llm_provider)

    answer = await pipeline.handle("best computer engineering colleges in Pune")

    assert answer.text == "PCCOE is a great choice [1]."
    assert len(answer.sources) == 1
    assert answer.sources[0].title == "PCCOE Admissions"
    assert answer.evaluation.faithfulness == 0.9
    assert answer.evaluation.context_precision == 0.9
    assert answer.evaluation.error is None


@pytest.mark.asyncio
async def test_no_search_results_short_circuits_before_generation():
    sub_query = "some obscure query"
    search_provider = FakeSearchProvider({})  # nothing matches -> empty results
    llm_provider = FakeLLMProvider(
        structured_response=QueryPlanResponse(
            intent="find something", complexity="simple", queries=[sub_query]
        ),
        # If AnswerGenerator were called it would return this - it must not be.
        generate_response="The sources do not contain enough information to answer.",
    )
    pipeline = build_pipeline(search_provider, llm_provider)

    answer = await pipeline.handle("some obscure query")

    assert answer.sources == ()
    assert "couldn't find any information" in answer.text
    assert answer.evaluation is None


@pytest.mark.asyncio
async def test_query_planner_fallback_still_flows_through_the_whole_pipeline():
    raw_question = "best computer engineering colleges in pune"
    search_provider = FakeSearchProvider(
        {
            raw_question: [
                SearchResult(
                    url="https://example.com/pccoe",
                    title="PCCOE Admissions",
                    snippet="PCCOE, Pune offers a well-regarded Computer Engineering program.",
                    source_query=raw_question,
                    provider_score=0.9,
                )
            ]
        }
    )
    llm_provider = FakeLLMProvider(
        raise_on_structured=RuntimeError("planner exploded"),
        generate_response="PCCOE is a great choice [1].",
    )
    pipeline = build_pipeline(search_provider, llm_provider)

    answer = await pipeline.handle(raw_question)

    # QueryPlanner fell back to a single sub-query = the raw question, which
    # is exactly what FakeSearchProvider was keyed on - proving the fallback
    # Query genuinely flows through search/dedup/rank/context/generation.
    assert len(answer.sources) == 1
    assert answer.sources[0].title == "PCCOE Admissions"


@pytest.mark.asyncio
async def test_evaluation_failure_does_not_crash_the_pipeline():
    sub_query = "best computer engineering colleges pune"
    search_provider = FakeSearchProvider(
        {
            sub_query: [
                SearchResult(
                    url="https://example.com/pccoe",
                    title="PCCOE Admissions",
                    snippet="PCCOE, Pune offers a well-regarded Computer Engineering program.",
                    source_query=sub_query,
                    provider_score=0.9,
                )
            ]
        }
    )
    llm_provider = FakeLLMProvider(
        structured_response=QueryPlanResponse(
            intent="find CE colleges", complexity="simple", queries=[sub_query]
        ),
        generate_response="PCCOE is a great choice [1].",
    )
    evaluator = FakeEvaluator(raise_exc=RuntimeError("ragas exploded"))
    pipeline = build_pipeline(search_provider, llm_provider, evaluator=evaluator)

    answer = await pipeline.handle("best computer engineering colleges in Pune")

    # The answer itself is unaffected - evaluation failing is non-blocking.
    assert answer.text == "PCCOE is a great choice [1]."
    assert answer.evaluation.error is not None
    assert answer.evaluation.faithfulness is None


@pytest.mark.asyncio
async def test_evaluation_uses_full_context_not_just_cited_sources():
    sub_query = "best computer engineering colleges pune"
    search_provider = FakeSearchProvider(
        {
            sub_query: [
                SearchResult(
                    url="https://example.com/pccoe",
                    title="PCCOE Admissions",
                    snippet="PCCOE, Pune offers a well-regarded Computer Engineering program.",
                    source_query=sub_query,
                    provider_score=0.9,
                ),
                SearchResult(
                    url="https://example.com/coep",
                    title="COEP",
                    snippet="COEP is a top-ranked government engineering college in Pune.",
                    source_query=sub_query,
                    provider_score=0.8,
                ),
            ]
        }
    )
    # Generated answer cites only source [1] (PCCOE), never mentions COEP.
    llm_provider = FakeLLMProvider(
        structured_response=QueryPlanResponse(
            intent="find CE colleges", complexity="simple", queries=[sub_query]
        ),
        generate_response="PCCOE is a great choice [1].",
    )

    received_contexts: list[str] = []

    class RecordingEvaluator(Evaluator):
        async def evaluate(self, question, answer, contexts):
            received_contexts.extend(contexts)
            return EvaluationResult(faithfulness=1.0, context_precision=1.0)

    pipeline = build_pipeline(search_provider, llm_provider, evaluator=RecordingEvaluator())

    answer = await pipeline.handle("best computer engineering colleges in Pune")

    # Only one source was cited, but both were passed to evaluation.
    assert len(answer.sources) == 1
    assert len(received_contexts) == 2


@pytest.mark.asyncio
async def test_empty_query_is_rejected_before_query_planning():
    class ExplodingLLMProvider(LLMProvider):
        async def generate_structured(self, prompt, schema, *, system_prompt=None):
            raise AssertionError("QueryPlanner should never be called for empty input")

        async def generate(self, prompt, *, system_prompt=None):
            raise AssertionError("AnswerGenerator should never be called for empty input")

    pipeline = build_pipeline(FakeSearchProvider({}), ExplodingLLMProvider())

    answer = await pipeline.handle("   ")

    assert answer.sources == ()
    assert answer.evaluation is None
    assert "between 1 and" in answer.text


@pytest.mark.asyncio
async def test_overlong_query_is_rejected_before_query_planning():
    class ExplodingLLMProvider(LLMProvider):
        async def generate_structured(self, prompt, schema, *, system_prompt=None):
            raise AssertionError("QueryPlanner should never be called for overlong input")

        async def generate(self, prompt, *, system_prompt=None):
            raise AssertionError("AnswerGenerator should never be called for overlong input")

    pipeline = build_pipeline(FakeSearchProvider({}), ExplodingLLMProvider())

    answer = await pipeline.handle("x" * 501)

    assert answer.evaluation is None
    assert "between 1 and" in answer.text


@pytest.mark.asyncio
async def test_answer_generation_failure_degrades_gracefully():
    sub_query = "best computer engineering colleges pune"
    search_provider = FakeSearchProvider(
        {
            sub_query: [
                SearchResult(
                    url="https://example.com/pccoe",
                    title="PCCOE Admissions",
                    snippet="PCCOE, Pune offers a well-regarded Computer Engineering program.",
                    source_query=sub_query,
                    provider_score=0.9,
                )
            ]
        }
    )

    class FailingLLMProvider(LLMProvider):
        async def generate_structured(self, prompt, schema, *, system_prompt=None):
            return QueryPlanResponse(
                intent="find CE colleges", complexity="simple", queries=[sub_query]
            )

        async def generate(self, prompt, *, system_prompt=None):
            raise RuntimeError("groq exploded after exhausting retries")

    pipeline = build_pipeline(search_provider, FailingLLMProvider())

    answer = await pipeline.handle("best computer engineering colleges in Pune")

    assert answer.sources == ()
    assert answer.evaluation is None
    assert "having trouble generating an answer" in answer.text
