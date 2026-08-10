"""ChatPipeline: the single use-case object chaining Phases 2-6 together,
plus evaluation (Phase 8) as a non-blocking final step.

Phase 10 adds a graceful-degradation ladder so handle() always returns an
Answer, never raises - the same self-contained-failure-handling pattern
QueryPlanner and EvaluationService already use. Three points can degrade:
invalid input (rejected before QueryPlanner is even called), zero sources
after search+build (AnswerGenerator is skipped entirely - there's nothing
grounded to generate from), and answer generation itself failing (Groq
exhausted its retries). All three return a synthetic Answer with
evaluation=None, which is how a synthetic message is distinguished from a
real generated-and-evaluated one - only a successfully generated Answer
ever reaches EvaluationService.
"""
from dataclasses import replace

from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.evaluation_service import EvaluationService
from src.application.query_planner import QueryPlanner
from src.application.search_orchestrator import SearchOrchestrator
from src.domain.entities import Answer, Query
from src.domain.interfaces import Ranker
from src.utils.logging import get_logger

logger = get_logger(__name__)


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
        stripped_query = user_query.strip()
        if not stripped_query or len(stripped_query) > self._max_query_length:
            logger.info("rejecting invalid query (length=%d)", len(stripped_query))
            return self._degraded_answer(
                user_query,
                "Please enter a question between 1 and "
                f"{self._max_query_length} characters.",
            )

        query = await self._query_planner.plan(stripped_query)
        raw_results = await self._search_orchestrator.search_all(
            query, self._max_results_per_query
        )
        deduped = self._deduplicator.deduplicate(raw_results)
        ranked = self._ranker.rank(deduped, query.original_text)
        sources = await self._context_builder.build(ranked)

        if not sources:
            logger.info("no sources found for query, skipping generation")
            return self._degraded_answer(
                user_query,
                "I couldn't find any information to answer that question.",
                query=query,
            )

        try:
            answer = await self._answer_generator.generate(query, sources)
        except Exception as exc:
            logger.warning("answer generation failed: %s", exc)
            return self._degraded_answer(
                user_query,
                "I'm having trouble generating an answer right now. Please try again.",
                query=query,
            )

        # Evaluated against the full source set ContextBuilder produced,
        # not answer.sources (only what the model chose to cite) - scoring
        # faithfulness against a model's own self-reported citations would
        # be circular.
        evaluation = await self._evaluation_service.evaluate(
            question=query.original_text,
            answer=answer.text,
            contexts=[source.content_used for source in sources],
        )
        return replace(answer, evaluation=evaluation)

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
