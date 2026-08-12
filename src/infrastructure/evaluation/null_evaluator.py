"""No-op Evaluator: returns an empty EvaluationResult instantly, with no
LLM calls and no I/O. Used by build_demo_pipeline() so the public
Streamlit demo can skip RAGAS entirely (extra Groq calls, latency, and
free-tier quota/rate-limit risk on a public-facing surface) without
EvaluationService or ChatPipeline needing to know the difference - both
already treat "no scores" as a normal, valid outcome (see
docs/decisions.md, 1.6), which is exactly what this returns.
"""
from src.domain.entities import EvaluationResult
from src.domain.interfaces import Evaluator


class NullEvaluator(Evaluator):
    async def evaluate(
        self, question: str, answer: str, contexts: list[str]
    ) -> EvaluationResult:
        return EvaluationResult()
