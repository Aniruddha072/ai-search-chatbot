"""ChatPipeline tested with the real SearchOrchestrator, Deduplicator,
HeuristicRanker, ContextBuilder, QueryPlanner, and AnswerGenerator -
faked only at the true I/O boundary (SearchProvider, LLMProvider,
ContentExtractor). Exercises the entire real chain offline.
"""
import pytest

from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.pipeline import ChatPipeline
from src.application.query_planner import QueryPlanner
from src.application.ranker import HeuristicRanker
from src.application.search_orchestrator import SearchOrchestrator
from src.config.prompts.query_planning import QueryPlanResponse
from src.domain.entities import SearchResult
from src.domain.interfaces import ContentExtractor, LLMProvider, SearchProvider


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


def build_pipeline(search_provider: SearchProvider, llm_provider: LLMProvider) -> ChatPipeline:
    return ChatPipeline(
        query_planner=QueryPlanner(llm_provider, timeout_seconds=5.0),
        search_orchestrator=SearchOrchestrator(search_provider, timeout_seconds=5.0),
        deduplicator=Deduplicator(),
        ranker=HeuristicRanker(),
        context_builder=ContextBuilder(
            content_extractor=FakeContentExtractor(),
            max_context_sources=5,
            context_token_budget=2500,
            content_fetch_timeout_seconds=5.0,
        ),
        answer_generator=AnswerGenerator(llm_provider, timeout_seconds=5.0),
        max_results_per_query=5,
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


@pytest.mark.asyncio
async def test_no_search_results_still_produces_an_answer_with_no_sources():
    sub_query = "some obscure query"
    search_provider = FakeSearchProvider({})  # nothing matches -> empty results
    llm_provider = FakeLLMProvider(
        structured_response=QueryPlanResponse(
            intent="find something", complexity="simple", queries=[sub_query]
        ),
        generate_response="The sources do not contain enough information to answer.",
    )
    pipeline = build_pipeline(search_provider, llm_provider)

    answer = await pipeline.handle("some obscure query")

    assert answer.sources == ()
    assert "do not contain enough information" in answer.text


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
