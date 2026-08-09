"""ChatPipeline: the single use-case object chaining Phases 2-6 together.

Happy-path only, deliberately. Catching/translating exceptions into a
single response shape and the graceful-degradation ladder are explicitly
Phase 10 checklist items, not this phase's - a failure here propagates
straight to the caller uncaught.
"""
from src.application.answer_generator import AnswerGenerator
from src.application.context_builder import ContextBuilder
from src.application.deduplicator import Deduplicator
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
        max_results_per_query: int,
    ) -> None:
        self._query_planner = query_planner
        self._search_orchestrator = search_orchestrator
        self._deduplicator = deduplicator
        self._ranker = ranker
        self._context_builder = context_builder
        self._answer_generator = answer_generator
        self._max_results_per_query = max_results_per_query

    async def handle(self, user_query: str) -> Answer:
        query = await self._query_planner.plan(user_query)
        raw_results = await self._search_orchestrator.search_all(
            query, self._max_results_per_query
        )
        deduped = self._deduplicator.deduplicate(raw_results)
        ranked = self._ranker.rank(deduped, query.original_text)
        sources = await self._context_builder.build(ranked)
        return await self._answer_generator.generate(query, sources)
