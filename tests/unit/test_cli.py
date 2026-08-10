"""Covers only the _print_evaluation blank-error regression - the rest of
cli.py (the stdin loop, Ctrl-C/EOF handling) is interactive UI behavior
verified by manual smoke test, not unit-testable in isolation.
"""
import pytest

from src.domain.entities import Answer, EvaluationResult, Query
from src.presentation.cli import _print_evaluation


def make_answer(evaluation: EvaluationResult | None) -> Answer:
    query = Query(
        original_text="best CE colleges in Pune",
        sub_queries=("best CE colleges in Pune",),
        intent="find colleges",
        complexity="simple",
    )
    return Answer(text="some answer", sources=(), query=query, evaluation=evaluation)


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
