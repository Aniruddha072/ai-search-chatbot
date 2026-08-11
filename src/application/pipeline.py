"""ChatPipeline: the single use-case object chaining Phases 2-6 together,
plus evaluation (Phase 8) as a non-blocking final step.

Phase 10 added a graceful-degradation ladder so handle() always returns an
Answer, never raises - the same self-contained-failure-handling pattern
QueryPlanner and EvaluationService already use. Three points can degrade:
invalid input (rejected before QueryPlanner is even called), zero sources
after search+build (AnswerGenerator is skipped entirely - there's nothing
grounded to generate from), and answer generation itself failing (Groq
exhausted its retries). All three return a synthetic Answer with
evaluation=None, which is how a synthetic message is distinguished from a
real generated-and-evaluated one - only a successfully generated Answer
ever reaches EvaluationService.

Phase 11 adds handle_streaming(), sharing everything through context
building with handle() via _prepare() - only the final generation+
evaluation step differs, because that's the only step with a genuinely
different shape (token-by-token vs. all-at-once). A generation failure
mid-stream is *not* caught the way handle()'s is: some of the real answer
may already be visible to whatever's consuming the stream (e.g. already
printed to a terminal), so there's nothing honest left to silently
degrade to - it propagates to the caller, same as pre-Phase-10 AnswerGenerator
behavior for the non-streaming path (Decision 6.1).
"""
import time
from dataclasses import replace
from typing import AsyncIterator, Awaitable, TypeVar

from src.application.answer_generator import AnswerGenerator, StreamedAnswer
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.evaluation_service import EvaluationService
from src.application.query_planner import QueryPlanner
from src.application.search_orchestrator import SearchOrchestrator
from src.domain.entities import Answer, Query, Source
from src.domain.interfaces import Ranker
from src.utils.logging import get_logger

logger = get_logger(__name__)

_T = TypeVar("_T")


async def _timed(timings: dict[str, float], stage: str, coro: Awaitable[_T]) -> _T:
    start = time.monotonic()
    try:
        return await coro
    finally:
        timings[stage] = time.monotonic() - start


def _log_turn_timings(timings: dict[str, float], turn_start: float) -> None:
    breakdown = " ".join(f"{stage}={duration:.2f}s" for stage, duration in timings.items())
    total = time.monotonic() - turn_start
    logger.info("turn timings: %s total=%.2fs", breakdown, total)


class ChatPipeline:
    def __init__(
        self,
        query_planner: QueryPlanner,
        search_orchestrator: SearchOrchestrator,
        deduplicator: Deduplicator,
        ranker: Ranker,
        context_builder: ContextBuilder,
        answer_generator: AnswerGenerator,
        evaluation_service: EvaluationService,
        max_results_per_query: int,
        max_query_length: int,
    ) -> None:
        self._query_planner = query_planner
        self._search_orchestrator = search_orchestrator
        self._deduplicator = deduplicator
        self._ranker = ranker
        self._context_builder = context_builder
        self._answer_generator = answer_generator
        self._evaluation_service = evaluation_service
        self._max_results_per_query = max_results_per_query
        self._max_query_length = max_query_length

    async def handle(self, user_query: str) -> Answer:
        turn_start = time.monotonic()
        timings: dict[str, float] = {}

        prepared = await self._prepare(user_query, timings)
        if isinstance(prepared, Answer):
            _log_turn_timings(timings, turn_start)
            return prepared
        query, sources = prepared

        try:
            answer = await _timed(
                timings, "generation", self._answer_generator.generate(query, sources)
            )
        except Exception as exc:
            logger.warning("answer generation failed: %s", exc)
            degraded = self._degraded_answer(
                user_query,
                "I'm having trouble generating an answer right now. Please try again later.",
                query=query,
            )
            _log_turn_timings(timings, turn_start)
            return degraded

        # Evaluated against the full source set ContextBuilder produced,
        # not answer.sources (only what the model chose to cite) - scoring
        # faithfulness against a model's own self-reported citations would
        # be circular.
        evaluation = await _timed(
            timings,
            "eval",
            self._evaluation_service.evaluate(
                question=query.original_text,
                answer=answer.text,
                contexts=[source.content_used for source in sources],
            ),
        )
        _log_turn_timings(timings, turn_start)
        return replace(answer, evaluation=evaluation)

    async def handle_streaming(self, user_query: str) -> "PipelineStream":
        turn_start = time.monotonic()
        timings: dict[str, float] = {}

        prepared = await self._prepare(user_query, timings)
        if isinstance(prepared, Answer):
            _log_turn_timings(timings, turn_start)
            return PipelineStream.completed(prepared)
        query, sources = prepared

        streamed_answer = self._answer_generator.generate_streaming(query, sources)
        return PipelineStream.streaming(
            streamed_answer,
            evaluation_service=self._evaluation_service,
            original_query=query.original_text,
            context_sources=sources,
            timings=timings,
            turn_start=turn_start,
        )

    async def _prepare(
        self, user_query: str, timings: dict[str, float]
    ) -> Answer | tuple[Query, tuple[Source, ...]]:
        """Validation through context-building - the prefix shared by
        handle() and handle_streaming(). Returns an already-final degraded
        Answer if there's nothing to generate from, otherwise the (Query,
        sources) generation needs. Records planning/search/context stage
        durations into the caller's timings dict as it goes, so a turn
        that degrades here still reports whatever stages actually ran.
        """
        stripped_query = user_query.strip()
        if not stripped_query or len(stripped_query) > self._max_query_length:
            logger.info("rejecting invalid query (length=%d)", len(stripped_query))
            return self._degraded_answer(
                user_query,
                "Please enter a question between 1 and "
                f"{self._max_query_length} characters.",
            )

        query = await _timed(timings, "planning", self._query_planner.plan(stripped_query))
        raw_results = await _timed(
            timings,
            "search",
            self._search_orchestrator.search_all(query, self._max_results_per_query),
        )
        deduped = self._deduplicator.deduplicate(raw_results)
        ranked = self._ranker.rank(deduped, query.original_text)
        sources = await _timed(timings, "context", self._context_builder.build(ranked))

        if not sources:
            logger.info("no sources found for query, skipping generation")
            return self._degraded_answer(
                user_query,
                "I couldn't find any information to answer that question.",
                query=query,
            )

        return query, sources

    @staticmethod
    def _degraded_answer(user_query: str, message: str, query: Query | None = None) -> Answer:
        if query is None:
            query = Query(
                original_text=user_query,
                sub_queries=(user_query or " ",),
                intent="invalid",
                complexity="unknown",
            )
        return Answer(text=message, sources=(), query=query)


class PipelineStream:
    """Returned by ChatPipeline.handle_streaming(). Async-iterate it for
    text chunks as they arrive; call get_answer() once fully consumed for
    the final Answer.

    Two construction paths, mirroring handle()'s two outcomes:
    streaming() wraps an in-progress AnswerGenerator.StreamedAnswer and
    attaches evaluation once consumed, exactly like handle()'s success
    path. completed() wraps an already-final degraded Answer (invalid
    input / zero sources) with nothing left to stream but its own message
    text, and no evaluation call - the streaming analogue of handle()'s
    degraded branches (Decision 10.4).
    """

    def __init__(self, chunks: AsyncIterator[str], finalize) -> None:
        self._chunks = chunks
        self._finalize = finalize

    def __aiter__(self) -> AsyncIterator[str]:
        return self._chunks

    async def get_answer(self) -> Answer:
        return await self._finalize()

    @classmethod
    def streaming(
        cls,
        streamed_answer: StreamedAnswer,
        *,
        evaluation_service: EvaluationService,
        original_query: str,
        context_sources: tuple[Source, ...],
        timings: dict[str, float],
        turn_start: float,
    ) -> "PipelineStream":
        # "generation" here spans stream acquisition through full
        # consumption by whoever's iterating (e.g. cli.py printing each
        # chunk), not just the underlying Groq call - there's no single
        # awaitable to wrap the way _timed() wraps handle()'s non-streaming
        # generate() call, since the tokens are produced as the caller
        # iterates, not inside one call this class controls.
        generation_start = time.monotonic()

        async def finalize() -> Answer:
            answer = streamed_answer.build_answer()
            timings["generation"] = time.monotonic() - generation_start
            evaluation = await _timed(
                timings,
                "eval",
                evaluation_service.evaluate(
                    question=original_query,
                    answer=answer.text,
                    contexts=[source.content_used for source in context_sources],
                ),
            )
            _log_turn_timings(timings, turn_start)
            return replace(answer, evaluation=evaluation)

        return cls(streamed_answer.__aiter__(), finalize)

    @classmethod
    def completed(cls, answer: Answer) -> "PipelineStream":
        async def chunks() -> AsyncIterator[str]:
            yield answer.text

        async def finalize() -> Answer:
            return answer

        return cls(chunks(), finalize)
