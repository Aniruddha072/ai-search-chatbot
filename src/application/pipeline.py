"""ChatPipeline: the single use-case object chaining Phases 2-6 together,
plus evaluation (Phase 8) as a non-blocking final step.

Happy-path only, deliberately. Catching/translating exceptions into a
single response shape and the graceful-degradation ladder are explicitly
Phase 10 checklist items, not this phase's - a failure here propagates
straight to the caller uncaught. EvaluationService is the one exception:
it's non-blocking by its own design (Decision 1.6/Phase 8), not because
ChatPipeline catches anything on its behalf.
"""
from dataclasses import replace

from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
from src.application.evaluation_service import EvaluationService
from src.application.query_planner import QueryPlanner
from src.application.search_orchestrator import SearchOrchestrator
from src.domain.entities import Answer
from src.domain.interfaces import Ranker


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
    ) -> None:
        self._query_planner = query_planner
        self._search_orchestrator = search_orchestrator
        self._deduplicator = deduplicator
        self._ranker = ranker
        self._context_builder = context_builder
        self._answer_generator = answer_generator
        self._evaluation_service = evaluation_service
        self._max_results_per_query = max_results_per_query

    async def handle(self, user_query: str) -> Answer:
        query = await self._query_planner.plan(user_query)
        raw_results = await self._search_orchestrator.search_all(
            query, self._max_results_per_query
        )
        deduped = self._deduplicator.deduplicate(raw_results)
        ranked = self._ranker.rank(deduped, query.original_text)
        sources = await self._context_builder.build(ranked)
        answer = await self._answer_generator.generate(query, sources)

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
