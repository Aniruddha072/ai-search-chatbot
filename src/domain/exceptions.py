"""Typed exceptions raised by infrastructure adapters, alongside the
domain ports they correspond to - same reasoning as everything else in
domain/: framework-agnostic, no external dependencies.

Infrastructure adapters catch the real SDK-specific exception (after
retries are exhausted) and re-raise as the matching type here - the same
anti-corruption-layer pattern already used for data (raw Tavily dict ->
SearchResult), now applied to errors.
"""


class PipelineError(Exception):
    """Base for every typed exception raised by an infrastructure adapter."""


class SearchProviderError(PipelineError):
    """A SearchProvider implementation failed after exhausting retries."""


class LLMGenerationError(PipelineError):
    """An LLMProvider implementation failed after exhausting retries."""


class EvaluationError(PipelineError):
    """An Evaluator implementation failed."""
