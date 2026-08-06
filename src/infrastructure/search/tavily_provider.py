"""Tavily adapter: the only place in the codebase that knows Tavily's
request/response shape. Translates Tavily's raw dicts into domain
SearchResult entities - domain and application code never see a raw
Tavily response.
"""
from tavily import AsyncTavilyClient

from src.domain.entities import SearchResult
from src.domain.interfaces import SearchProvider


class TavilyProvider(SearchProvider):
    def __init__(self, api_key: str) -> None:
        self._client = AsyncTavilyClient(api_key=api_key)

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        response = await self._client.search(query=query, max_results=max_results)

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
        ]
