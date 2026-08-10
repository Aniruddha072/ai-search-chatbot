import pytest

from src.domain.exceptions import EvaluationError
from src.infrastructure.evaluation.ragas_evaluator import RagasEvaluator


class _FakeMetricResult:
    def __init__(self, value: float) -> None:
        self.value = value


class _FakeMetric:
    def __init__(self, value: float) -> None:
        self._value = value
        self.received_kwargs: dict | None = None

    async def ascore(self, **kwargs) -> _FakeMetricResult:
        self.received_kwargs = kwargs
        return _FakeMetricResult(self._value)


def make_evaluator(faithfulness_value: float, context_precision_value: float) -> RagasEvaluator:
    evaluator = RagasEvaluator(api_key="test-key", model="test-model")
    evaluator._faithfulness = _FakeMetric(faithfulness_value)
    evaluator._context_precision = _FakeMetric(context_precision_value)
    return evaluator


@pytest.mark.asyncio
async def test_evaluate_returns_both_scores():
    evaluator = make_evaluator(faithfulness_value=0.9, context_precision_value=0.8)

    result = await evaluator.evaluate(
        question="q", answer="a", contexts=["ctx one", "ctx two"]
    )

    assert result.faithfulness == 0.9
    assert result.context_precision == 0.8
    assert result.answer_relevancy is None
    assert result.error is None


@pytest.mark.asyncio
async def test_evaluate_passes_question_answer_contexts_to_both_metrics():
    evaluator = make_evaluator(faithfulness_value=1.0, context_precision_value=1.0)

    await evaluator.evaluate(question="my question", answer="my answer", contexts=["ctx"])

    for metric in (evaluator._faithfulness, evaluator._context_precision):
        assert metric.received_kwargs == {
            "user_input": "my question",
            "response": "my answer",
            "retrieved_contexts": ["ctx"],
        }


class _FailingMetric:
    async def ascore(self, **kwargs):
        raise RuntimeError("ragas metric exploded")


@pytest.mark.asyncio
async def test_evaluate_wraps_failures_as_evaluation_error():
    evaluator = make_evaluator(faithfulness_value=0.9, context_precision_value=0.8)
    evaluator._faithfulness = _FailingMetric()

    with pytest.raises(EvaluationError):
        await evaluator.evaluate(question="q", answer="a", contexts=["ctx"])
