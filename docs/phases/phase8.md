# Phase 8 — RAGAS Evaluation

**Commit:** `06b3826` (feat(evaluation): implement RagasEvaluator and EvaluationService)

## What we built
- `src/infrastructure/evaluation/ragas_evaluator.py`: `RagasEvaluator`, implementing `Evaluator`. Wraps Groq as RAGAS's judge LLM via `instructor.from_provider("groq/...")`, running `ragas.metrics.collections.Faithfulness` and `ContextPrecisionWithoutReference` concurrently via `asyncio.gather`. No error handling, no timeout - a plain adapter, same role as `TavilyProvider`.
- `src/application/evaluation_service.py`: `EvaluationService`, the non-blocking wrapper - `asyncio.wait_for` + try/except around `RagasEvaluator`, always returns an `EvaluationResult` (never raises, never returns bare `None`).
- `src/domain/entities.py`: added `evaluation: EvaluationResult | None = None` to `Answer` (defaults to `None`, backward-compatible with every prior phase's `Answer(...)` calls).
- `src/application/pipeline.py`: `ChatPipeline.handle()` now calls `EvaluationService` as the final step, scoring against the *full* source set `ContextBuilder` produced - not `answer.sources` (only what the model chose to cite) - then attaches the result via `dataclasses.replace(answer, evaluation=evaluation)` since `Answer` is frozen.
- `src/bootstrap.py`: wires `RagasEvaluator` (its own instructor-based Groq client - not the shared `GroqClient` instance, since instructor needs its own client construction path) and `EvaluationService` into `ChatPipeline`.
- New `Settings` field: `evaluation_timeout_seconds` (15.0, slightly longer than other timeouts - two concurrent metric calls, each potentially multi-step internally).
- `pyproject.toml`: `ragas`'s real sub-dependencies listed explicitly (numpy, datasets, tiktoken, nest-asyncio, appdirs, diskcache, typer, rich, openai, tqdm, instructor, pillow, langchain, langchain-core, `langchain-community>=0.3.27,<0.4` pinned, langchain-openai). `ragas` itself is deliberately **not** a normal dependency - see below.
- `README.md`: an extra documented Setup step, `pip install --no-deps ragas==0.4.3`, with the reason linked to Decision 8.1.
- Five test files/additions: `test_ragas_evaluator.py` (constructed for real, `._faithfulness`/`._context_precision` swapped for fakes - same pattern as swapping `provider._client` in Phase 2), `test_evaluation_service.py` (success/exception/timeout, always returns a result), `test_pipeline.py` additions (evaluation populates `Answer.evaluation`; evaluator failure doesn't crash the pipeline; evaluation is scored against the full context, not just cited sources - verified with a `RecordingEvaluator`), and a gated `tests/integration/test_ragas_evaluator.py`.

## What we learned

This phase involved more real-world debugging than any prior one - four separate, unrelated blockers, each resolved by direct investigation rather than assumption:

1. **`pip install ragas` failed outright.** It has a hard, unconditional dependency on `scikit-network` (a C-extension graph library), which has zero prebuilt Windows wheels for *any* Python version (confirmed by probing 3.12/3.13/3.14 explicitly - not a Python-3.14-specific gap). Static analysis of the wheel's source showed `scikit-network` is only imported by `ragas/testset/graph.py` (synthetic testset generation) - never by `ragas/__init__.py`, `evaluation.py`, `metrics/__init__.py`, or `llms/__init__.py`. Resolved with `pip install --no-deps` plus explicitly installing ragas's other real dependencies.
2. **The same import bug existed in the newest release, not just an old one.** Both `ragas==0.2.15` (tested first) and `ragas==0.4.3` (the actual latest) unconditionally import `langchain_community.chat_models.vertexai.ChatVertexAI` at module load time - a submodule removed in `langchain-community` 0.4.x. "Just use the latest version" wouldn't have avoided this. Fixed with a precise pin (`langchain-community>=0.3.27,<0.4`) rather than downgrading the whole langchain family - checked that version's own requirements were already satisfied by what was installed, so no further cascade was needed.
3. **`instructor.from_openai(groq_client)` rejected our Groq client** with `ClientError: Client must be an instance of one of: OpenAI, AsyncOpenAI. Got: AsyncGroq` - a strict `isinstance` check, despite Groq's SDK being intentionally OpenAI-API-shaped. `instructor.from_provider("groq/model-name", ...)` is the actually-supported path and worked on the first real test.
4. **`AnswerRelevancy` needs an embeddings model** - confirmed by reading its class hierarchy (`MetricWithEmbeddings`) - and Groq doesn't serve one. Verified directly: a real call to `client.embeddings.create(model="text-embedding-3-small", ...)` returned a 404 `model_not_found`, not assumed from the model list alone.

Every one of these was caught by installing/reading/calling the real thing, not by trusting documentation or general expectations about "the latest version" or "OpenAI-compatible" SDKs.

## Key design decisions
- **8.1** — `ragas==0.4.3` is installed via `pip install --no-deps` plus its real dependencies listed explicitly in `pyproject.toml`; `ragas` itself is intentionally absent from the normal dependency list, with the extra install step documented in README. Chosen over installing Visual C++ Build Tools (which would let `scikit-network` build normally) because it requires no system-level change and the feature `scikit-network` supports isn't used here anyway.
- **8.2** — `AnswerRelevancy` is dropped from scope entirely rather than added via a new embeddings provider (`sentence-transformers` or OpenAI). Only `Faithfulness` and `ContextPrecisionWithoutReference` are wired - both pure LLM-judge, no new provider category introduced for a project deliberately scoped to Tavily + Groq.
- **8.3** — `Answer` gained an `evaluation` field (Phase 1 entity extended) rather than changing `ChatPipeline.handle()`'s return type to a tuple - keeps `handle() -> Answer` consistent with how the roadmap describes it throughout, with the answer now optionally carrying its own score.
- **8.4** — Evaluation scores against the *full* `ContextBuilder` output, not `answer.sources` (the cited subset) - scoring faithfulness against a model's own self-reported citations would be circular. Verified with a dedicated test using a source the model never cited.
- **8.5** — `RagasEvaluator` does not reuse the shared `GroqClient`/`AsyncGroq` instance from Decision 7.1's "reused client" optimization - `instructor.from_provider` builds its own client via its own construction path, so there's nothing to share here. Noted explicitly rather than silently diverging from the established pattern.

## Challenges faced
Four real, unrelated environment/library issues in one phase (detailed above) - more than any prior phase combined. All resolved before writing any application code, using the same "verify against the real thing" discipline established in Phases 2, 4, 5, and 6, just applied more times in a row than usual.
