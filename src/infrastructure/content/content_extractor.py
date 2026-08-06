"""trafilatura adapter: fetches a URL and extracts its main text content.

trafilatura's fetch_url/extract are both synchronous, blocking calls (no
native async client), so the whole fetch+parse sequence runs inside
asyncio.to_thread - that keeps the event loop free without needing to
split "async fetch" from "thread-offloaded parse" separately.
"""
import asyncio

import trafilatura

from src.domain.interfaces import ContentExtractor


class TrafilaturaContentExtractor(ContentExtractor):
    async def extract(self, url: str) -> str | None:
        return await asyncio.to_thread(self._extract_sync, url)

    @staticmethod
    def _extract_sync(url: str) -> str | None:
        html = trafilatura.fetch_url(url)
        if html is None:
            return None
        return trafilatura.extract(html)
