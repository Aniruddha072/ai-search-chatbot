from src.domain.entities import ConversationTurn
from src.presentation.conversation_context import build_conversation_context


def test_no_messages_yields_an_empty_context():
    context = build_conversation_context([], max_turns=2)

    assert context.turns == ()


def test_pairs_up_a_user_and_assistant_message_into_one_turn():
    messages = [
        {"role": "user", "content": "best colleges in Pune?"},
        {"role": "assistant", "content": "COEP, VIT, and PCCOE are top picks."},
    ]

    context = build_conversation_context(messages, max_turns=2)

    assert context.turns == (
        ConversationTurn(
            question="best colleges in Pune?",
            answer_summary="COEP, VIT, and PCCOE are top picks.",
        ),
    )


def test_a_trailing_unanswered_question_is_not_turned_into_a_turn():
    messages = [
        {"role": "user", "content": "best colleges in Pune?"},
        {"role": "assistant", "content": "COEP, VIT, and PCCOE are top picks."},
        {"role": "user", "content": "which one is cheapest?"},  # being answered right now
    ]

    context = build_conversation_context(messages, max_turns=2)

    assert len(context.turns) == 1
    assert context.turns[0].question == "best colleges in Pune?"


def test_only_the_most_recent_max_turns_are_kept():
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "q3"},
        {"role": "assistant", "content": "a3"},
    ]

    context = build_conversation_context(messages, max_turns=2)

    assert [turn.question for turn in context.turns] == ["q2", "q3"]


def test_long_answers_are_truncated_to_bound_prompt_size():
    long_answer = "x" * 1000
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": long_answer},
    ]

    context = build_conversation_context(messages, max_turns=2)

    assert len(context.turns[0].answer_summary) == 300


def test_max_turns_zero_disables_history_entirely():
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]

    context = build_conversation_context(messages, max_turns=0)

    assert context.turns == ()
