"""
Lightweight post-answer evaluation.

This applies Module 6's faithfulness concept in the simplest form that
still actually works: one extra structured-output LLM call that checks
whether the answer's claims are actually supported by the search results
the agent retrieved.

This is deliberately NOT a full RAGAS harness with datasets and
experiment tracking -- that's a real next step (see README), not
something a v1 learning build needs. This one function is the
"Evaluate" stage from the Module 7 architecture, kept as small as
possible while still being a genuine check rather than a placeholder.
"""
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI

from config import Config


class FaithfulnessCheck(BaseModel):
    """Structured verdict from the fact-checking pass."""

    is_faithful: bool = Field(
        description="True if every claim in the answer is supported by the provided sources"
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Specific claims in the answer that are NOT supported by the sources",
    )
    confidence_note: str = Field(
        description="One sentence explaining the verdict"
    )


def evaluate_faithfulness(question: str, answer: str, sources_text: str) -> FaithfulnessCheck:
    """Check whether `answer` is actually supported by `sources_text`.

    Deliberately uses a fresh model call rather than reusing the agent's
    own conversation -- a model grading its own work in the same context
    tends to rubber-stamp itself. A separate call with only the raw
    inputs is a cheap way to reduce that bias (Module 1's reflection
    section, Module 6's calibration point).
    """
    if not sources_text.strip():
        return FaithfulnessCheck(
            is_faithful=False,
            unsupported_claims=["No sources were retrieved to check the answer against."],
            confidence_note="No search results were available for verification.",
        )

    model = ChatGoogleGenerativeAI(
        model=Config.MODEL_NAME,
        google_api_key=Config.GOOGLE_API_KEY,
    )
    judge = model.with_structured_output(FaithfulnessCheck)

    prompt = (
        "You are a strict fact-checker. Given a question, an answer, and the "
        "source material the answer was supposedly based on, determine whether "
        "every factual claim in the answer is actually supported by the sources. "
        "Do not judge whether the answer is well-written -- only whether it is "
        "grounded in the given sources.\n\n"
        f"Question: {question}\n\n"
        f"Answer: {answer}\n\n"
        f"Sources:\n{sources_text[:6000]}"  # keep the judge call cheap and fast
    )
    return judge.invoke(prompt)
