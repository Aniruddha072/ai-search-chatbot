"""Domain entities: plain, immutable data. No I/O, no external libraries,
no knowledge of Tavily/Groq/RAGAS. Every other layer depends on these
shapes; these shapes depend on nothing.
"""
from dataclasses import dataclass

MIN_SUB_QUERIES = 1
MAX_SUB_QUERIES = 5


@dataclass(frozen=True)
class SearchResult:
    """One raw hit from a search provider, for a single sub-query."""

    url: str
    title: str
    snippet: str
    source_query: str
    content: str | None = None
    provider_score: float | None = None
    published_date: str | None = None


@dataclass(frozen=True)
class Query:
    """The output of query planning: the user's original question, decomposed
    into 1-5 concrete search queries.

    The 1-5 bound is enforced here, not just in the planner's prompt -
    an out-of-range Query object cannot exist, regardless of which code
    path constructs one.
    """

    original_text: str
    sub_queries: tuple[str, ...]
    intent: str
    complexity: str

    def __post_init__(self) -> None:
        count = len(self.sub_queries)
        if not (MIN_SUB_QUERIES <= count <= MAX_SUB_QUERIES):
            raise ValueError(
                f"sub_queries must contain {MIN_SUB_QUERIES}-{MAX_SUB_QUERIES} "
                f"queries, got {count}"
            )


@dataclass(frozen=True)
class Source:
    """A ranked, deduplicated search result that made it into the LLM's
    context - with the citation index the answer will reference as [index].
    """

    index: int
    url: str
    title: str
    content_used: str


@dataclass(frozen=True)
class Answer:
    """The final grounded answer plus the sources it was built from."""

    text: str
    sources: tuple[Source, ...]
    query: Query


@dataclass(frozen=True)
class EvaluationResult:
    """Reference-free RAGAS scores for one answer.

    All three scores are optional and `error` is set instead of raising,
    because evaluation must never block returning an answer to the user
    (see docs/decisions.md, 1.6) - a failed evaluation is a valid, expected
    outcome, not an exceptional one.
    """

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    error: str | None = None
