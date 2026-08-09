"""Turns a Query + ranked/budgeted Source tuple into a grounded, cited
Answer via Groq's capable model.

Unlike QueryPlanner, failures are not caught here - there's no safe
fallback for "produce a grounded answer" the way "search for the raw
question" is a safe fallback for planning. A timeout or API error
propagates to the caller; deciding what the user sees is a ChatPipeline
(Phase 7) / resilience (Phase 10) concern, not this component's.
"""
import asyncio
import re

from src.config.prompts.answer_generation import SYSTEM_PROMPT
from src.domain.entities import Answer, Query, Source
from src.domain.interfaces import LLMProvider

_CITATION_RE = re.compile(r"\[(\d+)\]")


class AnswerGenerator:
    def __init__(self, llm_provider: LLMProvider, timeout_seconds: float) -> None:
        self._llm_provider = llm_provider
        self._timeout_seconds = timeout_seconds

    async def generate(self, query: Query, sources: tuple[Source, ...]) -> Answer:
        prompt = self._build_prompt(query, sources)

        text = await asyncio.wait_for(
            self._llm_provider.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT),
            timeout=self._timeout_seconds,
        )

        cited_sources = self._extract_cited_sources(text, sources)
        return Answer(text=text, sources=cited_sources, query=query)

    @staticmethod
    def _build_prompt(query: Query, sources: tuple[Source, ...]) -> str:
        source_blocks = "\n\n".join(
            f"[{source.index}] Title: {source.title}\nContent: {source.content_used}"
            for source in sources
        )
        return f"Sources:\n{source_blocks}\n\nQuestion: {query.original_text}"

    @staticmethod
    def _extract_cited_sources(
        text: str, sources: tuple[Source, ...]
    ) -> tuple[Source, ...]:
        by_index = {source.index: source for source in sources}
        cited_indexes = {int(match) for match in _CITATION_RE.findall(text)}
        valid_indexes = sorted(cited_indexes & by_index.keys())
        return tuple(by_index[i] for i in valid_indexes)
