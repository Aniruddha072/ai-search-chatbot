"""Public-facing Streamlit chat UI - Phase 14's presentation-layer adapter.
Reuses build_demo_pipeline() (bootstrap.py) exactly like cli.py reuses
build_chat_pipeline(); no pipeline logic is duplicated here. The demo
pipeline wires a NullEvaluator instead of the CLI's real RagasEvaluator,
so it never makes the extra Groq calls RAGAS needs - see the README's
Evaluation section for why a public demo intentionally skips that.

Run locally:
    streamlit run src/presentation/streamlit_app.py

One asyncio.run() per turn, and a fresh build_demo_pipeline() inside it -
deliberately NOT cached across turns via st.cache_resource. Verified live:
GroqClient/TavilyProvider's async HTTP clients bind to whichever event
loop is running when they're first used, and asyncio.run() tears its loop
down when it returns, so a client reused from a *second* asyncio.run()
call raises "RuntimeError: Event loop is closed" the moment it tries to
use its old connection. A fresh pipeline (and fresh clients) per turn,
fully constructed and torn down inside one asyncio.run() call, sidesteps
this entirely - the same one-loop-per-unit-of-work model cli.py already
uses, just scoped to a turn instead of the whole process. The unclosed
clients are left for garbage collection rather than given an explicit
close() (verified live: this doesn't raise) - matching the CLI's own
process-exit cleanup model rather than adding new lifecycle methods to
already-shipped infrastructure classes just for this one caller.

This also rules out st.write_stream() passed a live async generator: its
own internal async-to-sync conversion spins up a *separate* new event
loop to consume it, which would cross loops with whatever loop
handle_streaming() already used for planning/search - the same failure
mode. Streaming is done by hand instead: iterate the chunks inside the
turn's own asyncio.run() call and update a placeholder as they arrive.

Phase 15 adds conversation memory: before each turn, build_conversation_context()
(conversation_context.py) turns the last few completed (question, answer)
pairs already sitting in st.session_state.messages into a bounded
ConversationContext, passed into handle_streaming() so QueryPlanner can
resolve a follow-up's pronouns/references. That helper lives in its own
module rather than here, since this file runs top-level Streamlit calls
on import and isn't itself unit-tested.
"""
import asyncio
import sys
import uuid
from pathlib import Path

# `streamlit run` executes this file directly (like `python script.py`), so
# Python puts this file's own directory - src/presentation - at sys.path[0],
# not the project root. `python -m src.presentation.cli` never had this
# problem (`-m` puts the invocation cwd on sys.path instead), but the same
# `from src...` absolute imports below need the project root on sys.path
# here too - verified live: without this, `streamlit run` fails immediately
# with ModuleNotFoundError: No module named 'src'.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from src.application.pipeline import ChatPipeline
from src.bootstrap import build_demo_pipeline
from src.config.settings import get_settings
from src.domain.entities import Answer, ConversationContext
from src.presentation.conversation_context import build_conversation_context
from src.utils.logging import configure_logging, get_logger, set_turn_id

logger = get_logger(__name__)

st.set_page_config(page_title="AI Search Chatbot", page_icon="🔎")
st.title("AI Search Chatbot")
st.caption(
    "Ask a question and get a grounded, cited answer built from a live web "
    "search. This public demo skips the RAGAS quality scores (Faithfulness, "
    "Context Precision) available through the project's CLI/evaluation "
    "pipeline - see the Evaluation section of the README for why."
)


@st.cache_resource
def _configure_logging_once() -> None:
    configure_logging(get_settings().log_level)


def _sources_markdown(answer: Answer) -> str:
    if not answer.sources:
        return ""
    lines = ["", "**Sources:**"]
    for source in answer.sources:
        lines.append(f"{source.index}. [{source.title}]({source.url})")
    return "\n".join(lines)


async def _run_turn(
    user_query: str, conversation: ConversationContext, placeholder
) -> str:
    set_turn_id(uuid.uuid4().hex[:8])
    pipeline: ChatPipeline = build_demo_pipeline()
    stream = await pipeline.handle_streaming(user_query, conversation)

    text = ""
    try:
        async for chunk in stream:
            text += chunk
            placeholder.markdown(text)
    except Exception as exc:
        logger.warning("streaming turn failed: %s", exc)
        message = "I ran into a problem while answering. Please try again later."
        placeholder.markdown(message)
        return message

    answer = await stream.get_answer()
    full_text = text + _sources_markdown(answer)
    placeholder.markdown(full_text)
    return full_text


_configure_logging_once()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_query = st.chat_input("Ask a question")
if user_query:
    # Built from messages as they stand *before* this turn's question is
    # appended below, so it only ever contains prior, completed turns.
    conversation = build_conversation_context(
        st.session_state.messages, get_settings().conversation_history_turns
    )

    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = asyncio.run(_run_turn(user_query, conversation, response_placeholder))

    st.session_state.messages.append({"role": "assistant", "content": full_response})
