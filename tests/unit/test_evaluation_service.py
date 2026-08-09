import asyncio

import pytest

from src.application.evaluation_service import EvaluationService
from src.domain.entities import EvaluationResult
from src.domain.interfaces import Evaluator


class FakeEvaluator(Evaluator):
    def __init__(
        self,
        result: EvaluationResult | None = None,
        raise_exc: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self._delay = delay

    async def evaluate(self, question: str, answer: str, contexts: list[str]) -> EvaluationResult:
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raise_exc:
            raise self._raise_exc
        return self._result


@pytest.mark.asyncio
async def test_returns_the_evaluator_result_on_success():
    expected = EvaluationResult(faithfulness=0.9, context_precision=0.85)
    service = EvaluationService(FakeEvaluator(result=expected), timeout_seconds=5.0)

    result = await service.evaluate("q", "a", ["ctx"])

    assert result == expected


@pytest.mark.asyncio
async def test_returns_error_result_without_raising_on_exception():
    service = EvaluationService(
        FakeEvaluator(raise_exc=RuntimeError("ragas exploded")), timeout_seconds=5.0
    )

    result = await service.evaluate("q", "a", ["ctx"])

    assert result.error is not None
    assert "ragas exploded" in result.error
    assert result.faithfulness is None
    assert result.context_precision is None


@pytest.mark.asyncio
async def test_returns_error_result_without_raising_on_timeout():
    service = EvaluationService(FakeEvaluator(delay=1.0), timeout_seconds=0.05)

    result = await service.evaluate("q", "a", ["ctx"])

    assert result.error is not None
    assert result.faithfulness is None
