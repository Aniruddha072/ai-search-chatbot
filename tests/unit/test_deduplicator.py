from src.application.deduplicator import Deduplicator
from src.domain.entities import SearchResult


def make_result(url: str, title: str = "Title", snippet: str = "Snippet") -> SearchResult:
    return SearchResult(url=url, title=title, snippet=snippet, source_query="q")


def test_empty_list_returns_empty_list():
    assert Deduplicator().deduplicate([]) == []


def test_exact_duplicate_urls_collapse_to_first_occurrence():
    first = make_result("https://example.com/a", title="First")
    duplicate = make_result("https://example.com/a", title="Second")

    result = Deduplicator().deduplicate([first, duplicate])

    assert result == [first]


def test_url_variants_are_treated_as_the_same_url():
    first = make_result("https://Example.com/a/")
    variant_query_params = make_result("https://example.com/a?utm_source=x")
    variant_trailing_slash_and_case = make_result("HTTPS://EXAMPLE.COM/a")

    result = Deduplicator().deduplicate(
        [first, variant_query_params, variant_trailing_slash_and_case]
    )

    assert result == [first]


def test_different_paths_are_not_deduplicated():
    a = make_result(
        "https://example.com/a",
        title="Weather forecast for Pune this week",
        snippet="Expect sunny skies and highs near 30C through Friday.",
    )
    b = make_result(
        "https://example.com/b",
        title="Top IT companies hiring in Pune",
        snippet="A list of the largest technology employers in the city.",
    )

    result = Deduplicator().deduplicate([a, b])

    assert result == [a, b]


def test_near_duplicate_content_on_different_urls_collapses_to_first():
    first = make_result(
        "https://site-one.com/article",
        title="Best Computer Engineering Colleges in Pune 2026",
        snippet="PCCOE, Pune is the best Computer engineering college in the area.",
    )
    syndicated = make_result(
        "https://site-two.com/copy",
        title="Best Computer Engineering Colleges in Pune 2026",
        snippet="PCCOE, Pune is the best Computer engineering college in the area!",
    )

    result = Deduplicator().deduplicate([first, syndicated])

    assert result == [first]


def test_similarity_threshold_is_configurable():
    a = make_result("https://a.com", title="Cats are great pets", snippet="They purr a lot.")
    b = make_result("https://b.com", title="Cats are nice pets", snippet="They purr often.")

    strict = Deduplicator(similarity_threshold=0.99).deduplicate([a, b])
    lenient = Deduplicator(similarity_threshold=0.5).deduplicate([a, b])

    assert strict == [a, b]
    assert lenient == [a]
