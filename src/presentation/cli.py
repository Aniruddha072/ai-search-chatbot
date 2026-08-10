"""Interactive terminal chat loop calling ChatPipeline. Run with:

    python -m src.presentation.cli

Reads one question per line from stdin, streams the generated answer to
stdout token-by-token as it arrives (Phase 11 - Decision 6.2's deferred
streaming), then prints sources and RAGAS scores once the answer is
complete. Ctrl-C or EOF (Ctrl-D) exits cleanly instead of a traceback.
Empty/oversized input isn't special-cased here - it flows through to
ChatPipeline.handle_streaming() exactly like any other question, and
comes back as the same degraded, single-chunk Answer Decision 10.4
already defines, so validation stays owned by the pipeline, not
duplicated in the presentation layer.
"""
import asyncio
import uuid

from src.application.pipeline import ChatPipeline
from src.bootstrap import build_chat_pipeline
from src.config.settings import get_settings
from src.domain.entities import Answer
from src.utils.logging import configure_logging, get_logger, set_turn_id

logger = get_logger(__name__)


async def _read_line(prompt: str) -> str:
    """input() blocks the whole interpreter, not just the calling
    coroutine. Running it in a worker thread keeps the event loop free -
    it makes no visible difference in this single-user loop today, but
    it's the correct pattern rather than a habit worth skipping.
    """
    return await asyncio.to_thread(input, prompt)


def _print_sources(answer: Answer) -> None:
    if not answer.sources:
        return
    print("\nSources:")
    for source in answer.sources:
        print(f"  [{source.index}] {source.title} - {source.url}")


def _print_evaluation(answer: Answer) -> None:
    evaluation = answer.evaluation
    if evaluation is None:
        return
    if evaluation.error:
        print(f"\n(evaluation unavailable: {evaluation.error})")
        return
    scores = []
    if evaluation.faithfulness is not None:
        scores.append(f"faithfulness={evaluation.faithfulness:.2f}")
    if evaluation.context_precision is not None:
        scores.append(f"context_precision={evaluation.context_precision:.2f}")
    if scores:
        print(f"\n(scores: {', '.join(scores)})")


async def _handle_turn(pipeline: ChatPipeline, user_query: str) -> None:
    set_turn_id(uuid.uuid4().hex[:8])
    stream = await pipeline.handle_streaming(user_query)

    try:
        async for chunk in stream:
            print(chunk, end="", flush=True)
    except Exception as exc:
        logger.warning("streaming turn failed: %s", exc)
        print("\n[response interrupted by an error]")
        return

    print()
    answer = await stream.get_answer()
    _print_sources(answer)
    _print_evaluation(answer)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    pipeline = build_chat_pipeline()

    print("AI Search Chatbot - ask a question (Ctrl-C or Ctrl-D to quit)\n")
    while True:
        try:
            user_query = await _read_line("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        try:
            await _handle_turn(pipeline, user_query)
        except KeyboardInterrupt:
            print("\nGoodbye.")
            return
        print()


if __name__ == "__main__":
    asyncio.run(main())
