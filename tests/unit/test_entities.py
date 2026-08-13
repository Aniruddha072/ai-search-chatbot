import dataclasses

import pytest

from src.domain.entities import (
    Answer,
    ConversationContext,
    ConversationTurn,
    EvaluationResult,
    Query,
    SearchResult,
    Source,
)


def make_query(n: int) -> Query:
    return Query(
        original_text="best computer engineering colleges in pune",
        sub_queries=tuple(f"sub query {i}" for i in range(n)),
        intent="comparison",
        complexity="high",
    )


@pytest.mark.parametrize("n", [1, 3, 5])
def test_query_accepts_one_to_five_sub_queries(n):
    query = make_query(n)

    assert len(query.sub_queries) == n


@pytest.mark.parametrize("n", [0, 6])
def test_query_rejects_out_of_range_sub_query_counts(n):
    with pytest.raises(ValueError):
        make_query(n)


def test_query_is_immutable():
    query = make_query(1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        query.original_text = "something else"


def test_query_sub_queries_cannot_be_mutated_in_place():
    query = make_query(1)

    with pytest.raises(AttributeError):
        query.sub_queries.append("a sneaky sixth query")


def test_query_is_hashable():
    query_a = make_query(2)
    query_b = make_query(2)

    assert hash(query_a) == hash(query_b)
    assert {query_a, query_b} == {query_a}


def test_search_result_defaults():
    result = SearchResult(
        url="https://example.com",
        title="Example",
        snippet="An example snippet.",
        source_query="example query",
    )

    assert result.content is None
    assert result.provider_score is None
    assert result.published_date is None


def test_answer_holds_sources_and_query():
    query = make_query(1)
    source = Source(index=1, url="https://example.com", title="Example", content_used="text")
    answer = Answer(text="The answer is X [1].", sources=(source,), query=query)

    assert answer.sources[0].index == 1
    assert answer.query is query


def test_evaluation_result_defaults_to_all_none():
    result = EvaluationResult()

    assert result.faithfulness is None
    assert result.answer_relevancy is None
    assert result.context_precision is None
    assert result.error is None


def test_conversation_context_defaults_to_no_turns():
    context = ConversationContext()

    assert context.turns == ()


def test_conversation_turn_holds_question_and_answer_summary():
    turn = ConversationTurn(
        question="which one is cheapest?", answer_summary="COEP is the cheapest."
    )

    assert turn.question == "which one is cheapest?"
    assert turn.answer_summary == "COEP is the cheapest."


def test_conversation_context_is_immutable():
    context = ConversationContext()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.turns = (ConversationTurn(question="q", answer_summary="a"),)
