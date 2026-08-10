"""Turns a Query + ranked/budgeted Source tuple into a grounded, cited
Answer via Groq's capable model.

Unlike QueryPlanner, failures are not caught here - there's no safe
fallback for "produce a grounded answer" the way "search for the raw
question" is a safe fallback for planning. A timeout or API error
propagates to the caller; deciding what the user sees is a ChatPipeline
(Phase 7) / resilience (Phase 10) concern, not this component's.

generate_streaming() exists alongside generate(), not instead of it -
citation parsing needs the complete answer text, which a partial stream
can't provide, but printing tokens as they arrive (Phase 11's CLI) needs
the stream. StreamedAnswer holds both: iterating it yields text chunks
as they arrive, and calling build_answer() afterward parses citations
from the accumulated text - one Groq call, not two. An async generator
can't itself return the built Answer (an `async def` containing `yield`
can only `return` with no value, verified before writing this), which is
exactly why StreamedAnswer is a small stateful wrapper instead of a bare
generator function.
"""
import asyncio
import re
from typing import AsyncIterator

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

        return self._build_answer(query, text, sources)

    def generate_streaming(
        self, query: Query, sources: tuple[Source, ...]
    ) -> "StreamedAnswer":
        prompt = self._build_prompt(query, sources)
        chunks = self._llm_provider.generate_stream(
            prompt=prompt, system_prompt=SYSTEM_PROMPT
        )
        return StreamedAnswer(
            chunks, query=query, sources=sources, chunk_timeout_seconds=self._timeout_seconds
        )

    @staticmethod
    def _build_prompt(query: Query, sources: tuple[Source, ...]) -> str:
        source_blocks = "\n\n".join(
            f"[{source.index}] Title: {source.title}\nContent: {source.content_used}"
            for source in sources
        )
        return f"Sources:\n{source_blocks}\n\nQuestion: {query.original_text}"

    @staticmethod
    def _build_answer(query: Query, text: str, sources: tuple[Source, ...]) -> Answer:
        cited_sources = AnswerGenerator._extract_cited_sources(text, sources)
        return Answer(text=text, sources=cited_sources, query=query)

    @staticmethod
    def _extract_cited_sources(
        text: str, sources: tuple[Source, ...]
    ) -> tuple[Source, ...]:
        by_index = {source.index: source for source in sources}
        cited_indexes = {int(match) for match in _CITATION_RE.findall(text)}
        valid_indexes = sorted(cited_indexes & by_index.keys())
        return tuple(by_index[i] for i in valid_indexes)


class StreamedAnswer:
    """Wraps an in-flight token stream from AnswerGenerator.generate_streaming().

    Async-iterate it to receive text chunks as they arrive (e.g. to print
    them). Once iteration is exhausted, build_answer() returns the final,
    citation-parsed Answer built from the accumulated text - calling it
    before the stream is exhausted returns an Answer built from whatever
    text has arrived so far, which is never what a caller wants, so
    callers are expected to always fully consume the stream first.

    Each chunk wait is individually timeout-bounded (chunk_timeout_seconds)
    rather than the whole stream having one fixed budget - a stream that
    keeps producing chunks within that window can run for as long as the
    answer takes; only a stall between chunks counts as a timeout.
    """

    def __init__(
        self,
        chunks: AsyncIterator[str],
        *,
        query: Query,
        sources: tuple[Source, ...],
        chunk_timeout_seconds: float,
    ) -> None:
        self._chunks = chunks
        self._query = query
        self._sources = sources
        self._chunk_timeout_seconds = chunk_timeout_seconds
        self._accumulated: list[str] = []

    async def __aiter__(self) -> AsyncIterator[str]:
        chunk_iter = self._chunks.__aiter__()
        while True:
            try:
                piece = await asyncio.wait_for(
                    chunk_iter.__anext__(), timeout=self._chunk_timeout_seconds
                )
            except StopAsyncIteration:
                return
            self._accumulated.append(piece)
            yield piece

    def build_answer(self) -> Answer:
        text = "".join(self._accumulated)
        return AnswerGenerator._build_answer(self._query, text, self._sources)
