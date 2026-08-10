"""Tavily adapter: the only place in the codebase that knows Tavily's
request/response shape. Translates Tavily's raw dicts into domain
SearchResult entities - domain and application code never see a raw
Tavily response.

Retries only genuinely transient failures (Tavily's own TimeoutError,
or a raw httpx.TransportError - Tavily's client uses httpx internally,
confirmed by reading its __init__). Non-transient failures (bad request,
invalid key, quota exceeded) are not retried - retrying those wastes
the attempt budget without any chance of succeeding. Either way, every
failure that survives is re-raised as SearchProviderError, so callers
never see a raw tavily-python or httpx exception type.
"""
import httpx
from tavily import AsyncTavilyClient
from tavily.errors import TimeoutError as TavilyTimeoutError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.domain.entities import SearchResult
from src.domain.exceptions import SearchProviderError
from src.domain.interfaces import SearchProvider


class TavilyProvider(SearchProvider):
    def __init__(
        self, api_key: str, max_retries: int = 3, retry_backoff_seconds: float = 0.5
    ) -> None:
        self._client = AsyncTavilyClient(api_key=api_key)
        self._retrying = AsyncRetrying(
            stop=stop_after_attempt(max_retries),
            wait=wait_fixed(retry_backoff_seconds),
            retry=retry_if_exception_type((TavilyTimeoutError, httpx.TransportError)),
            reraise=True,
        )

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            response = await self._retrying(
                self._client.search, query=query, max_results=max_results
            )
        except Exception as exc:
            raise SearchProviderError(f"Tavily search failed for {query!r}: {exc}") from exc

        return [
            SearchResult(
                url=item["url"],
                title=item["title"],
                snippet=item["content"],
                source_query=query,
                provider_score=item.get("score"),
                published_date=item.get("published_date"),
            )
            for item in response["results"]
            if item["url"].startswith(("http://", "https://"))
        ]
