"""Covers the _print_evaluation blank-error regression, the
KeyboardInterrupt-scope regression (GitHub issue #2), and _handle_turn /
_print_sources against a fake pipeline/stream. _read_line, main()'s loop,
and the __main__ guard genuinely need real stdin/process interaction and
stay verified by manual smoke test instead.
"""
import pytest

from src.domain.entities import Answer, EvaluationResult, Query, Source
from src.presentation import cli
from src.presentation.cli import _print_evaluation, _print_sources


def make_query() -> Query:
    return Query(
        original_text="best CE colleges in Pune",
        sub_queries=("best CE colleges in Pune",),
        intent="find colleges",
        complexity="simple",
    )


def make_answer(evaluation: EvaluationResult | None, sources: tuple[Source, ...] = ()) -> Answer:
    return Answer(text="some answer", sources=sources, query=make_query(), evaluation=evaluation)


class _FakeStream:
    """Duck-types PipelineStream: async-iterable chunks, then get_answer()."""

    def __init__(self, chunks: list[str], answer: Answer, raise_after: int | None = None) -> None:
        self._chunks = chunks
        self._answer = answer
        self._raise_after = raise_after

    async def _chunk_gen(self):
        for i, chunk in enumerate(self._chunks):
            if self._raise_after is not None and i == self._raise_after:
                raise RuntimeError("mid-stream failure")
            yield chunk

    def __aiter__(self):
        return self._chunk_gen()

    async def get_answer(self) -> Answer:
        return self._answer


class _FakePipeline:
    def __init__(self, stream: _FakeStream) -> None:
        self._stream = stream

    async def handle_streaming(self, user_query: str) -> _FakeStream:
        return self._stream


def test_blank_error_string_still_prints_evaluation_unavailable(capsys):
    """A regression guard for the real bug: EvaluationResult(error="")
    is falsy, so a naive `if evaluation.error:` check treats a genuine
    (if uninformative) failure as if no error occurred at all, and
    prints nothing. _print_evaluation must use `is not None` instead.
    """
    answer = make_answer(EvaluationResult(error=""))

    _print_evaluation(answer)

    captured = capsys.readouterr()
    assert "evaluation unavailable" in captured.out


def test_named_error_prints_the_exception_name(capsys):
    answer = make_answer(EvaluationResult(error="TimeoutError"))

    _print_evaluation(answer)

    captured = capsys.readouterr()
    assert "evaluation unavailable: TimeoutError" in captured.out


def test_successful_evaluation_prints_scores_not_unavailable(capsys):
    answer = make_answer(EvaluationResult(faithfulness=0.9, context_precision=0.8))

    _print_evaluation(answer)

    captured = capsys.readouterr()
    assert "evaluation unavailable" not in captured.out
    assert "faithfulness=0.90" in captured.out
    assert "context_precision=0.80" in captured.out


def test_no_evaluation_prints_nothing(capsys):
    answer = make_answer(None)

    _print_evaluation(answer)

    captured = capsys.readouterr()
    assert captured.out == ""


@pytest.mark.asyncio
async def test_evaluation_service_blank_exception_flows_through_to_cli_output(capsys):
    """End-to-end regression for the exact real-world chain: a blank-
    message exception -> EvaluationService's fallback -> _print_evaluation
    correctly surfacing it, instead of the original silent-swallow bug.
    """
    from src.application.evaluation_service import EvaluationService
    from src.domain.interfaces import Evaluator

    class BlankFailingEvaluator(Evaluator):
        async def evaluate(self, question, answer, contexts):
            raise RuntimeError()

    service = EvaluationService(BlankFailingEvaluator(), timeout_seconds=5.0)
    evaluation = await service.evaluate("q", "a", ["ctx"])
    answer = make_answer(evaluation)

    _print_evaluation(answer)

    captured = capsys.readouterr()
    assert "evaluation unavailable: RuntimeError" in captured.out


def test_run_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    """Regression test for GitHub issue #2: asyncio.run() cancels the
    running task and re-raises KeyboardInterrupt from its own top-level
    frame, after main() has already been torn down - no try/except placed
    inside main()'s coroutine can ever catch it. run() must catch it at
    that outer scope instead, exactly where asyncio.run() is called.
    """

    def fake_asyncio_run(coro):
        coro.close()  # avoid a "coroutine was never awaited" warning
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli.asyncio, "run", fake_asyncio_run)

    cli.run()  # must not raise

    captured = capsys.readouterr()
    assert "Goodbye." in captured.out


def test_print_sources_with_no_sources_prints_nothing(capsys):
    _print_sources(make_answer(None, sources=()))

    captured = capsys.readouterr()
    assert captured.out == ""


@pytest.mark.asyncio
async def test_read_line_returns_the_input_value(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: f"echo:{prompt}")

    result = await cli._read_line("> ")

    assert result == "echo:> "


@pytest.mark.asyncio
async def test_handle_turn_streams_chunks_then_prints_sources_and_evaluation(capsys):
    source = Source(index=1, url="https://example.com", title="Example", content_used="...")
    evaluation = EvaluationResult(faithfulness=0.9, context_precision=0.8)
    answer = make_answer(evaluation, sources=(source,))
    pipeline = _FakePipeline(_FakeStream(["Paris ", "is ", "the capital."], answer))

    await cli._handle_turn(pipeline, "what is the capital of france?")

    captured = capsys.readouterr()
    assert "Paris is the capital." in captured.out
    assert "Sources:\n  [1] Example - https://example.com" in captured.out
    assert "faithfulness=0.90" in captured.out


@pytest.mark.asyncio
async def test_handle_turn_prints_interruption_message_on_mid_stream_failure(capsys):
    answer = make_answer(None)
    pipeline = _FakePipeline(_FakeStream(["partial ", "more"], answer, raise_after=1))

    await cli._handle_turn(pipeline, "a question")

    captured = capsys.readouterr()
    assert "partial " in captured.out
    assert "[response interrupted by an error]" in captured.out
