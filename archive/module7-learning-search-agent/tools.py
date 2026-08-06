"""
Tools available to the search agent.

Just one tool for this v1 build: Tavily web search. Adding a second tool
later (e.g. Apify for a specific known site, per Module 5) means adding
one function here and one line in agent.py -- nothing else changes.
"""
from langchain_tavily import TavilySearch

from config import Config


def get_search_tool() -> TavilySearch:
    """Build the Tavily search tool with this project's standard settings.

    Note: TavilySearch's own docstring/schema is what the model sees when
    deciding whether to call it (Module 2's docstring-quality point),
    we don't need to write a custom @tool wrapper here since TavilySearch
    already ships a good one, but if you rename or restrict it later,
    that's the file to edit.
    """
    return TavilySearch(
        max_results=Config.MAX_SEARCH_RESULTS,
        search_depth=Config.SEARCH_DEPTH,
    )
