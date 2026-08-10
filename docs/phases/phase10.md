# Phase 10 — Resilience Hardening

**Commit:** _(pending)_

## What we built
- `src/domain/exceptions.py`: `PipelineError` base plus `SearchProviderError`, `LLMGenerationError`, `EvaluationError` - one typed exception per infrastructure port, same anti-corruption-layer pattern already used for data (raw Tavily dict -> `SearchResult`), now applied to errors.
- `src/infrastructure/search/tavily_provider.py`: wraps `self._client.search(...)` in a `tenacity.AsyncRetrying` instance targeting `tavily.errors.TimeoutError` + `httpx.TransportError` only; any surviving failure re-raises as `SearchProviderError`. Also drops any result whose `url` isn't absolute (`http://`/`https://`) - the Tavily relative-URL finding deferred from Phase 9.
- `src/infrastructure/llm/groq_client.py`: same `AsyncRetrying` treatment on both `generate()` and `generate_structured()`, targeting `groq.APIConnectionError`, `RateLimitError`, `InternalServerError`; failures re-raise as `LLMGenerationError`. JSON/schema validation failures in `generate_structured()` are deliberately left unwrapped - `QueryPlanner` already catches broad `Exception` around that call and falls back to a single-query plan.
- `src/infrastructure/evaluation/ragas_evaluator.py`: no retry (see Decision 10.6), but failures now wrap as `EvaluationError` instead of leaking a raw `ragas`/`instructor` exception.
- `src/application/pipeline.py`: `ChatPipeline.handle()` gained three degradation branches, all returning a synthetic `Answer` with `evaluation=None` instead of raising - empty/oversized input (rejected before `QueryPlanner` is even called), zero sources after search+context-building (skips `AnswerGenerator` entirely), and answer-generation failure (catches and returns a fixed message).
- `src/config/settings.py` / `.env.example`: three new fields - `max_query_length` (500), `max_retry_attempts` (3), `retry_backoff_seconds` (0.5).
- `src/bootstrap.py`: wires the new settings into `TavilyProvider`, `GroqClient`, and `ChatPipeline`.
- Test files: `test_tavily_provider.py`, `test_groq_client.py`, `test_ragas_evaluator.py` gained retry-success/retry-exhaustion/non-retryable-immediate-fail cases per adapter; `test_pipeline.py` gained cases for empty input, oversized input, zero-sources short-circuit (rewritten - it previously asserted the *old* always-generate behavior), and generation-failure degradation.

## What we learned
- `tenacity.AsyncRetrying` used as an instance (not the `@retry` decorator) is the right shape when the retry policy depends on constructor-injected settings rather than being fixed at class-definition time - `await self._retrying(func, *args, **kwargs)` reads naturally and keeps the policy testable in isolation (verified with a standalone script before writing production code).
- The zero-sources short-circuit changed an existing Phase 7 test's assumption: it previously asserted the pipeline still called `AnswerGenerator` on an empty source set and trusted the model to say "I don't have enough information." Phase 10 changed that to skip generation entirely - cheaper, and removes any chance of the model hallucinating past an empty context. The old test had to be rewritten, not just extended.
- Leaving `QueryPlanner`/`SearchOrchestrator`/`EvaluationService`'s existing broad `except Exception` catches broad (not narrowed to the new `PipelineError`) was a deliberate choice, not an oversight - see Decision 10.5.

## Key design decisions
See `docs/decisions.md`, Decisions 10.1-10.7, for the full reasoning:
- 10.1: typed exception hierarchy in `domain/exceptions.py`, one per port.
- 10.2: retry-worthy exception sets verified against real Groq/Tavily SDK source, not guessed.
- 10.3: `max_retry_attempts`/`retry_backoff_seconds` are `Settings` fields, not constructor constants.
- 10.4: `ChatPipeline.handle()` always returns `Answer`, never raises.
- 10.5: existing broad `except Exception` catches stay broad by design.
- 10.6: `RagasEvaluator` wraps failures but does not retry them.
- 10.7: the Tavily relative-URL fix lives in `TavilyProvider.search()`.

## Challenges faced
None outside the expected scope - the design from the previous session's planning held up as-scoped. The main mechanical cost was updating five test files to match new required constructor params (`max_query_length` on `ChatPipeline`) and one genuinely-changed pipeline behavior (zero-sources short-circuit), all caught immediately by running the full unit suite rather than assuming green. The gated integration suite (`RUN_INTEGRATION_TESTS=1`, 5 tests against real Tavily/Groq) passed unchanged, confirming the retry/URL-filter wiring didn't disturb the real happy path.
