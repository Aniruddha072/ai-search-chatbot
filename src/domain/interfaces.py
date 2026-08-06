"""Domain interfaces (ports): abstract contracts that infrastructure/
adapters implement and application/ code depends on. Nothing in this
file knows about Tavily, Groq, RAGAS, Redis, or any other concrete
technology - that's the whole point of putting them here.

Each is an abc.ABC with @abstractmethod, so a class that doesn't
implement every method fails at instantiation time with a clear
TypeError, rather than failing later with an AttributeError deep
inside the pipeline.
"""
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from src.domain.entities import EvaluationResult, SearchResult

T = TypeVar("T")


class SearchProvider(ABC):
    """One search backend (Tavily today; Serper or others later).
    async because it's a network call the orchestrator will run
    concurrently with several others via asyncio.gather.
    """

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...


class LLMProvider(ABC):
    """One LLM backend (Groq). Two methods because the pipeline needs both
    shapes of output: free-text (the final grounded answer) and structured
    (the query planner's JSON plan). `schema` is typically a Pydantic model
    class; T is left unbound here so this file has no dependency on
    Pydantic - the binding happens wherever generate_structured is called.
    """

    @abstractmethod
    async def generate(
        self, prompt: str, *, system_prompt: str | None = None
    ) -> str: ...

    @abstractmethod
    async def generate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T: ...


class Ranker(ABC):
    """Scores and orders deduplicated search results. Not async: this is
    pure in-memory computation (keyword overlap, recency, provider score),
    not I/O - see architecture doc 6.4 for why this starts as a heuristic
    rather than an embedding-based reranker.
    """

    @abstractmethod
    def rank(
        self, results: list[SearchResult], original_query: str
    ) -> list[SearchResult]: ...


class Evaluator(ABC):
    """Reference-free answer quality scoring (RAGAS). async because it
    makes its own LLM-judge calls.
    """

    @abstractmethod
    async def evaluate(
        self, question: str, answer: str, contexts: list[str]
    ) -> EvaluationResult: ...


class Cache(ABC):
    """Key/value cache with TTL. `Any` for the value because different
    call sites cache different things (query plans, raw search results).
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
