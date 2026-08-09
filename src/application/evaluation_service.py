"""Non-blocking wrapper around an Evaluator: enforces a timeout and never
raises. Always returns an EvaluationResult - error is set and both scores
stay None on any failure, using the shape Phase 1 designed for exactly
this case (see domain/entities.py, EvaluationResult).
"""
import asyncio

from src.domain.entities import EvaluationResult
from src.domain.interfaces import Evaluator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EvaluationService:
    def __init__(self, evaluator: Evaluator, timeout_seconds: float) -> None:
        self._evaluator = evaluator
        self._timeout_seconds = timeout_seconds

    async def evaluate(
        self, question: str, answer: str, contexts: list[str]
    ) -> EvaluationResult:
        try:
            return await asyncio.wait_for(
                self._evaluator.evaluate(question, answer, contexts),
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            logger.warning("evaluation failed, returning null scores: %s", exc)
            return EvaluationResult(error=str(exc))
