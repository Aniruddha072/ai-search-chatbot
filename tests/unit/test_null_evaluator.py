import pytest

from src.domain.entities import EvaluationResult
from src.infrastructure.evaluation.null_evaluator import NullEvaluator


@pytest.mark.asyncio
async def test_evaluate_returns_an_empty_evaluation_result_with_no_error():
    result = await NullEvaluator().evaluate(
        question="What is the capital of France?",
        answer="Paris.",
        contexts=["Paris is the capital of France."],
    )

    assert result == EvaluationResult()
    assert result.error is None
    assert result.faithfulness is None
    assert result.context_precision is None
