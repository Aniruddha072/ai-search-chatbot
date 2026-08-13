"""Builds a bounded ConversationContext from Streamlit's session-state
message list. Kept in its own module, separate from streamlit_app.py,
because that file runs top-level Streamlit calls (st.set_page_config(),
st.chat_input(), ...) on import - pulling it into a test would mean
executing those outside a real Streamlit script run. Splitting this pure
function out mirrors Phase 12's precedent of extracting cli.py helpers
specifically so they're unit-testable in isolation.
"""
from src.domain.entities import ConversationContext, ConversationTurn

_ANSWER_SUMMARY_CHARS = 300


def build_conversation_context(
    messages: list[dict[str, str]], max_turns: int
) -> ConversationContext:
    """Pairs up consecutive user/assistant messages into ConversationTurns,
    keeping only the most recent `max_turns`. A trailing user message with
    no assistant reply yet (the question currently being answered) is
    never turned into a turn - there's nothing to pair it with. Each
    stored answer is truncated to _ANSWER_SUMMARY_CHARS so the planning
    prompt this feeds into doesn't grow with the full cited answer text.
    """
    if max_turns <= 0:
        return ConversationContext()

    turns: list[ConversationTurn] = []
    pending_question: str | None = None
    for message in messages:
        if message["role"] == "user":
            pending_question = message["content"]
        elif message["role"] == "assistant" and pending_question is not None:
            turns.append(
                ConversationTurn(
                    question=pending_question,
                    answer_summary=message["content"][:_ANSWER_SUMMARY_CHARS],
                )
            )
            pending_question = None

    return ConversationContext(turns=tuple(turns[-max_turns:]))
