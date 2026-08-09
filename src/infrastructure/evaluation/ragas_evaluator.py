"""RAGAS adapter: the only place that knows RAGAS's API/response shape.

Wraps Groq as RAGAS's judge LLM via instructor.from_provider("groq/...") -
NOT instructor.from_openai(groq_client), which rejects AsyncGroq with a
strict isinstance check despite Groq's SDK being API-shape-compatible
with OpenAI's. Verified against the live API before writing this.

Only Faithfulness and ContextPrecisionWithoutReference are wired -
AnswerRelevancy is deliberately not implemented: it requires an
embeddings model, and Groq doesn't serve one (verified: a real
embeddings call 404s). See docs/decisions.md, 8.x.

No error handling, no timeout - matches TavilyProvider/ContentExtractor's
role as a plain adapter. EvaluationService (application layer) is where
resilience lives, the same relationship Decision 2.2 established between
SearchOrchestrator and SearchProvider.
"""
import asyncio

import instructor
from ragas.llms import InstructorLLM
from ragas.metrics.collections import ContextPrecisionWithoutReference, Faithfulness

from src.domain.entities import EvaluationResult
from src.domain.interfaces import Evaluator


class RagasEvaluator(Evaluator):
    def __init__(self, api_key: str, model: str) -> None:
        instructor_client = instructor.from_provider(
            f"groq/{model}", async_client=True, api_key=api_key
        )
        llm = InstructorLLM(client=instructor_client, model=model, provider="groq")
        self._faithfulness = Faithfulness(llm=llm)
        self._context_precision = ContextPrecisionWithoutReference(llm=llm)

    async def evaluate(
        self, question: str, answer: str, contexts: list[str]
    ) -> EvaluationResult:
        faithfulness_result, context_precision_result = await asyncio.gather(
            self._faithfulness.ascore(
                user_input=question, response=answer, retrieved_contexts=contexts
            ),
            self._context_precision.ascore(
                user_input=question, response=answer, retrieved_contexts=contexts
            ),
        )
        return EvaluationResult(
            faithfulness=faithfulness_result.value,
            context_precision=context_precision_result.value,
        )
