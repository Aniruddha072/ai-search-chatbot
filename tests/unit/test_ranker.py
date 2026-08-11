from datetime import date, timedelta

from src.application.ranker import HeuristicRanker
from src.domain.entities import SearchResult


def make_result(
    url: str = "https://example.com",
    title: str = "",
    snippet: str = "",
    provider_score: float | None = None,
    published_date: str | None = None,
) -> SearchResult:
    return SearchResult(
        url=url,
        title=title,
        snippet=snippet,
        source_query="q",
        provider_score=provider_score,
        published_date=published_date,
    )


def test_rank_preserves_all_results_only_reorders():
    results = [make_result(url=f"https://example.com/{i}") for i in range(4)]

    ranked = HeuristicRanker().rank(results, original_query="anything")

    assert len(ranked) == len(results)
    assert set(r.url for r in ranked) == set(r.url for r in results)


def test_higher_keyword_overlap_ranks_first_when_other_factors_equal():
    query = "best computer engineering colleges in pune"
    strong_match = make_result(
        title="Best Computer Engineering Colleges in Pune",
        snippet="A full ranking of computer engineering colleges in Pune.",
        provider_score=0.5,
    )
    weak_match = make_result(
        title="Colleges",
        snippet="A general directory.",
        provider_score=0.5,
    )

    ranked = HeuristicRanker().rank([weak_match, strong_match], original_query=query)

    assert ranked[0] is strong_match


def test_higher_provider_score_ranks_first_when_other_factors_equal():
    query = "unrelated query terms"
    high_score = make_result(title="X", snippet="Y", provider_score=0.9)
    low_score = make_result(title="X", snippet="Y", provider_score=0.1)

    ranked = HeuristicRanker().rank([low_score, high_score], original_query=query)

    assert ranked[0] is high_score


def test_missing_provider_score_does_not_crash_and_is_treated_as_zero():
    query = "query"
    missing = make_result(title="a", snippet="b", provider_score=None)

    ranked = HeuristicRanker().rank([missing], original_query=query)

    assert ranked == [missing]


def test_missing_published_date_does_not_crash():
    result = make_result(published_date=None)

    ranked = HeuristicRanker().rank([result], original_query="q")

    assert ranked == [result]


def test_more_recent_result_ranks_higher_when_other_factors_equal():
    today = date.today().isoformat()
    two_years_ago = (date.today() - timedelta(days=730)).isoformat()

    recent = make_result(title="a", snippet="b", provider_score=0.5, published_date=today)
    old = make_result(title="a", snippet="b", provider_score=0.5, published_date=two_years_ago)

    ranked = HeuristicRanker().rank([old, recent], original_query="a b")

    assert ranked[0] is recent


def test_unparseable_published_date_falls_back_to_neutral_without_crashing():
    result = make_result(published_date="not-a-date")

    ranked = HeuristicRanker().rank([result], original_query="q")

    assert ranked == [result]


def test_query_with_no_alphanumeric_tokens_does_not_divide_by_zero():
    result = make_result(title="a", snippet="b", provider_score=0.5)

    ranked = HeuristicRanker().rank([result], original_query="???")

    assert ranked == [result]


def test_future_published_date_ranks_above_an_older_result():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    two_years_ago = (date.today() - timedelta(days=730)).isoformat()

    future = make_result(title="a", snippet="b", provider_score=0.5, published_date=tomorrow)
    old = make_result(title="a", snippet="b", provider_score=0.5, published_date=two_years_ago)

    ranked = HeuristicRanker().rank([old, future], original_query="a b")

    assert ranked[0] is future
