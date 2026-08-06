"""Turns a ranked, deduplicated list[SearchResult] into the tuple[Source, ...]
that AnswerGenerator (a later phase) will cite from: picks the top-K
results, decides which need their full page fetched instead of relying on
the snippet, and enforces a hard token budget across everything combined.
"""
import asyncio

from src.domain.entities import SearchResult, Source
from src.domain.interfaces import ContentExtractor
from src.utils.logging import get_logger
from src.utils.token_counter import count_tokens, truncate_to_token_count

logger = get_logger(__name__)

DEFAULT_FULL_FETCH_CANDIDATE_COUNT = 3
DEFAULT_THIN_SNIPPET_WORD_THRESHOLD = 40
MIN_USEFUL_TOKENS = 20


class ContextBuilder:
    def __init__(
        self,
        content_extractor: ContentExtractor,
        max_context_sources: int,
        context_token_budget: int,
        content_fetch_timeout_seconds: float,
        full_fetch_candidate_count: int = DEFAULT_FULL_FETCH_CANDIDATE_COUNT,
        thin_snippet_word_threshold: int = DEFAULT_THIN_SNIPPET_WORD_THRESHOLD,
    ) -> None:
        self._content_extractor = content_extractor
        self._max_context_sources = max_context_sources
        self._context_token_budget = context_token_budget
        self._content_fetch_timeout_seconds = content_fetch_timeout_seconds
        self._full_fetch_candidate_count = full_fetch_candidate_count
        self._thin_snippet_word_threshold = thin_snippet_word_threshold

    async def build(self, results: list[SearchResult]) -> tuple[Source, ...]:
        top_results = results[: self._max_context_sources]
        texts = await self._resolve_texts(top_results)
        return self._apply_token_budget(top_results, texts)

    async def _resolve_texts(self, top_results: list[SearchResult]) -> list[str]:
        texts = [result.snippet for result in top_results]

        candidate_indexes = [
            i
            for i, result in enumerate(top_results)
            if i < self._full_fetch_candidate_count and self._is_thin(result.snippet)
        ]
        if not candidate_indexes:
            return texts

        fetches = [
            asyncio.wait_for(
                self._content_extractor.extract(top_results[i].url),
                timeout=self._content_fetch_timeout_seconds,
            )
            for i in candidate_indexes
        ]
        fetched_or_errors = await asyncio.gather(*fetches, return_exceptions=True)

        for i, fetched in zip(candidate_indexes, fetched_or_errors):
            if isinstance(fetched, Exception):
                logger.warning(
                    "full-fetch failed, falling back to snippet: %r (%s)",
                    top_results[i].url,
                    fetched,
                )
                continue
            if fetched:
                texts[i] = fetched

        return texts

    def _is_thin(self, snippet: str) -> bool:
        return len(snippet.split()) < self._thin_snippet_word_threshold

    def _apply_token_budget(
        self, top_results: list[SearchResult], texts: list[str]
    ) -> tuple[Source, ...]:
        sources: list[Source] = []
        remaining_budget = self._context_token_budget

        for result, text in zip(top_results, texts):
            tokens = count_tokens(text)
            truncated = False
            if tokens <= remaining_budget:
                content_used = text
            elif remaining_budget >= MIN_USEFUL_TOKENS:
                content_used = truncate_to_token_count(text, remaining_budget)
                truncated = True
            else:
                break

            sources.append(
                Source(
                    index=len(sources) + 1,
                    url=result.url,
                    title=result.title,
                    content_used=content_used,
                )
            )
            remaining_budget -= count_tokens(content_used)

            if truncated:
                break

        return tuple(sources)
