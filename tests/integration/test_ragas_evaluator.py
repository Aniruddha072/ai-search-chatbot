"""Real call to Groq via RAGAS/instructor. Skipped by default - opt in
with RUN_INTEGRATION_TESTS=1, matching the other integration tests' pattern.
"""
import os

import pytest
from dotenv import load_dotenv

from src.infrastructure.evaluation.ragas_evaluator import RagasEvaluator

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="set RUN_INTEGRATION_TESTS=1 to run tests that call the real Groq API",
)


@pytest.mark.asyncio
async def test_real_ragas_evaluator_scores_a_grounded_answer():
    load_dotenv()
    evaluator = RagasEvaluator(
        api_key=os.environ["GROQ_API_KEY"], model="llama-3.3-70b-versatile"
    )

    result = await evaluator.evaluate(
        question="What are good computer engineering colleges in Pune?",
        answer=(
            "PCCOE, Pune is a good option for Computer Engineering as it "
            "offers a well-regarded program with modern labs."
        ),
        contexts=[
            "PCCOE, Pune offers a well-regarded Computer Engineering "
            "program with modern labs."
        ],
    )

    assert result.error is None
    assert result.faithfulness is not None
    assert result.context_precision is not None
    assert 0.0 <= result.faithfulness <= 1.0
    assert 0.0 <= result.context_precision <= 1.0
