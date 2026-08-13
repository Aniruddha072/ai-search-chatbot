# Roadmap & Task Checklist

Related docs: [Architecture](architecture.md) · [Decisions & tradeoffs](decisions.md) · [Phase build logs](phases/)

Each phase produces something runnable/testable before moving on — no phase
depends on an unbuilt future phase. Current status is tracked in the
[root README](../README.md#documentation); a build log for each completed
phase (what was built, what was learned, challenges, commit hash) lives in
[phases/](phases/).

---

## 1. Phased implementation roadmap

**Phase 0 — Project scaffolding**
Repo structure, `pyproject.toml`, dependency setup, `.env.example`, settings loader, logging setup.

**Phase 1 — Domain layer**
Entities and interfaces only. No implementations. This is the contract everything else is built against.

**Phase 2 — Search integration**
`TavilyProvider` implementing `SearchProvider`. `SearchOrchestrator` with parallel fan-out, timeouts, partial-failure tolerance. Testable standalone: give it a hardcoded list of queries, get back merged raw results.

**Phase 3 — Dedup + ranking**
`Deduplicator` and default `Ranker`. Testable standalone against fixture search results.

**Phase 4 — Context building**
`ContextBuilder` with token budgeting and the snippet-vs-full-fetch rule; `ContentExtractor` for the full-fetch path.

**Phase 5 — Query planning**
`QueryPlanner` calling Groq's fast model with structured output, schema validation, capped at 5 queries.

**Phase 6 — Answer generation**
`AnswerGenerator` calling Groq's capable model with the grounded/cited prompt.

**Phase 7 — Pipeline wiring**
`ChatPipeline` composes phases 2–6 into one call. First true end-to-end run, still without evaluation.

**Phase 8 — RAGAS evaluation**
`EvaluationService` wrapping faithfulness/answer relevancy/context precision, wired into the pipeline as a non-blocking final step.

**Phase 9 — Caching**
`InMemoryCache`, wired into query planning and search stages.

**Phase 10 — Resilience hardening**
Retries, per-stage timeouts, typed exceptions, graceful degradation paths from [decisions.md, Error Handling Strategy](decisions.md#6-error-handling-strategy).

**Phase 11 — CLI presentation layer**
Interactive terminal chat loop calling `ChatPipeline`, with streamed answer output.

**Phase 12 — Testing**
Unit tests per application-layer component (providers mocked), integration tests gated behind an env flag for real Tavily/Groq calls.

**Phase 13 — Observability & polish**
Structured per-turn logging/timing, README, architecture/decisions docs finalization for the internship writeup.

**Phase 14 — Public Streamlit demo**
`streamlit_app.py`, a minimal presentation-layer adapter over the same `ChatPipeline` (via a new `build_demo_pipeline()`), deployed free on Streamlit Community Cloud. Skips RAGAS scoring on the public surface (`NullEvaluator`) - the real evaluation pipeline stays available and documented through the CLI. A future production-style deployment could add `presentation/api.py` (FastAPI) in front of the same pipeline, but that's explicitly out of scope here - see the Phase 14 checklist below.

**Phase 15 — Conversation-aware query resolution**
`QueryPlanner.plan()` gains an optional `conversation` parameter so a follow-up question ("which one is cheapest?") resolves against a bounded, recent window of prior turns instead of being planned in isolation - folded into the existing Groq call rather than a second LLM call, with a cache-key fix so two different conversations can't collide on one cached plan. Proposed and designed in [GitHub issue #3](https://github.com/Aniruddha072/ai-search-chatbot/issues/3) before any code was written.

---

## 2. Task checklist

Each box is independently completable and independently testable.

### Phase 0 — Scaffolding
- [x] Initialize repo, `pyproject.toml`, dependency groups (runtime vs dev/test)
- [x] Create folder structure from architecture.md §4 (empty `__init__.py` files)
- [x] `.env.example` with `TAVILY_API_KEY`, `GROQ_API_KEY`
- [x] `config/settings.py` using `pydantic-settings` to load and validate env vars
- [x] `utils/logging.py` — structured logger with per-turn correlation ID support

### Phase 1 — Domain layer
- [x] `domain/entities.py`: `Query`, `SearchResult`, `Source`, `Answer`, `EvaluationResult` dataclasses
- [x] `domain/interfaces.py`: `SearchProvider` ABC (`async search(query, max_results) -> list[SearchResult]`)
- [x] `domain/interfaces.py`: `LLMProvider` ABC (`async generate(prompt, **kwargs) -> str`, plus a structured-output variant)
- [x] `domain/interfaces.py`: `Ranker` ABC (`rank(results, original_query) -> list[SearchResult]`)
- [x] `domain/interfaces.py`: `Evaluator` ABC (`async evaluate(question, answer, contexts) -> EvaluationResult`)
- [x] `domain/interfaces.py`: `Cache` ABC (`get`, `set` with TTL)

### Phase 2 — Search integration
- [x] `infrastructure/search/tavily_provider.py`: implement `SearchProvider` using Tavily's async client
- [x] Map Tavily's raw response into `SearchResult` entities
- [x] `application/search_orchestrator.py`: `asyncio.gather` fan-out with `return_exceptions=True`
- [x] Add per-query timeout (`asyncio.wait_for`) inside the orchestrator
- [x] Unit test: orchestrator with a mocked `SearchProvider` that fails on one of three queries — assert partial results returned
- [x] Integration test (env-gated): one real Tavily call end-to-end

### Phase 3 — Dedup + ranking
- [x] `application/deduplicator.py`: URL normalization (strip query params/fragments) pass
- [x] `application/deduplicator.py`: near-duplicate content pass (title+snippet similarity)
- [x] `application/ranker.py`: keyword-overlap scoring against original query
- [x] `application/ranker.py`: combine with recency + provider score into final rank
- [x] Unit tests with fixture result sets containing intentional duplicates

### Phase 4 — Context building
- [x] `utils/token_counter.py`: token counting helper (tiktoken or model-appropriate tokenizer)
- [x] `application/context_builder.py`: top-K selection from ranked results
- [x] `application/context_builder.py`: thin-snippet detection rule triggering full-fetch
- [x] `infrastructure/content/content_extractor.py`: fetch + extract main content (trafilatura), thread-offloaded
- [x] `application/context_builder.py`: token-budget enforcement with per-source truncation
- [x] Unit tests: budget enforcement never exceeds the configured cap

### Phase 5 — Query planning
- [x] `config/prompts/query_planning.py`: prompt + JSON schema (intent, complexity, queries[1..5])
- [x] `infrastructure/llm/groq_client.py`: structured-output call method using the fast model
- [x] `application/query_planner.py`: call + schema validation + hard cap/floor enforcement (1–5)
- [x] Fallback path: on planner failure, fall back to a single query = raw user input
- [x] Unit tests: mocked Groq responses covering valid, malformed, and over-5-queries cases

### Phase 6 — Answer generation
- [x] `config/prompts/answer_generation.py`: grounded/cite-or-refuse system prompt
- [x] `infrastructure/llm/groq_client.py`: generation method using the capable model (non-streaming; streaming implemented in Phase 11 once the CLI existed to actually consume it - Decision 6.2)
- [x] `application/answer_generator.py`: build indexed source list, call Groq, parse citation markers into `Answer`
- [x] Unit tests: mocked Groq output with citations mapped back to correct `Source` objects

### Phase 7 — Pipeline wiring
- [x] `application/pipeline.py`: `ChatPipeline.handle(user_query) -> Answer` composing phases 2–6
- [x] `bootstrap.py`: composition root wiring concrete providers from settings into `ChatPipeline`
- [x] Manual end-to-end smoke test with a real question (made automated/repeatable as a gated integration test rather than a one-off script)

### Phase 8 — RAGAS evaluation
- [x] `infrastructure/evaluation/ragas_evaluator.py`: implement `Evaluator`, wrap RAGAS with Groq as judge LLM
- [x] Wire faithfulness, context_precision as concurrent metric calls (answer_relevancy dropped - needs embeddings, Groq has none; see Decision 8.2)
- [x] `application/evaluation_service.py`: non-blocking wrapper — catches evaluator errors, returns an `EvaluationResult` with `error` set on failure
- [x] Wire into `ChatPipeline` as the final step
- [x] Unit test: evaluator failure does not propagate to pipeline failure

### Phase 9 — Caching
- [x] `infrastructure/cache/memory_cache.py`: TTL dict-based `Cache` implementation
- [x] Wire query-plan caching into `QueryPlanner`
- [x] Wire per-sub-query result caching into `SearchOrchestrator`
- [x] Unit tests: cache hit skips the underlying call (assert mock not called twice)

### Phase 10 — Resilience hardening
- [x] Add `tenacity` retry (`AsyncRetrying`) to Tavily and Groq client calls, targeting verified retry-worthy exception sets only
- [x] Define typed exceptions: `SearchProviderError`, `LLMGenerationError`, `EvaluationError`
- [x] Each adapter (`TavilyProvider`, `GroqClient`, `RagasEvaluator`) wraps its own failures into the matching typed exception
- [x] Implement the degradation ladder from [decisions.md, Error Handling Strategy](decisions.md#6-error-handling-strategy) (invalid-input, zero-sources, generation-failed paths) — `ChatPipeline.handle()` always returns an `Answer`, never raises
- [x] Input validation at pipeline entry (empty/oversized query rejection, `max_query_length`)
- [x] Fold the Phase 9-deferred Tavily relative-URL finding into `TavilyProvider.search()` (drop non-absolute URLs)

### Phase 11 — CLI presentation
- [x] `presentation/cli.py`: interactive loop reading stdin, calling `ChatPipeline`
- [x] Stream answer tokens to stdout as they arrive
- [x] Print sources and RAGAS scores after the answer
- [x] Handle Ctrl-C / empty input gracefully

### Phase 12 — Testing
- [x] Unit test coverage for every `application/` module (providers/LLM mocked)
- [x] Integration test suite behind `RUN_INTEGRATION_TESTS=1` env flag
- [x] At least one full end-to-end integration test with real Tavily + Groq

### Phase 13 — Observability & polish
- [x] Per-stage timing captured and logged per turn (planning/search/context/generation/eval durations)
- [x] README: setup instructions, architecture summary, how to run
- [x] Finalize architecture.md/decisions.md with any deviations made during implementation

### Phase 14 — Public Streamlit demo
- [x] `infrastructure/evaluation/null_evaluator.py`: no-op `Evaluator`, instant `EvaluationResult()`, no I/O
- [x] `bootstrap.py`: extract shared wiring into a private helper; add `build_demo_pipeline()` (NullEvaluator) alongside unchanged `build_chat_pipeline()` (real RagasEvaluator)
- [x] `presentation/streamlit_app.py`: chat UI reusing `ChatPipeline.handle_streaming()`, streams answers + renders sources, reuses the CLI's friendly degraded-turn wording
- [x] Root `requirements.txt` for Streamlit Cloud's install step, deliberately excluding ragas/numpy/datasets/langchain/etc
- [x] README: Live Demo section + dedicated Evaluation section documenting Faithfulness/Context Precision, why the public demo skips them, and the live-verified evaluation result
- [x] Live-verify locally: real Tavily/Groq calls through the Streamlit UI, including a second turn in the same session (this caught and fixed a real event-loop-reuse bug - see Decision 14.3)
- [ ] Deploy to Streamlit Community Cloud (manual step: GitHub OAuth + secrets entry, done by the project owner, not part of this repo's code)

**Future work, not implemented here:** a production-style deployment could add `presentation/api.py` (FastAPI) in front of the same `ChatPipeline`, with a separate frontend - reusing the pipeline exactly as `cli.py` and `streamlit_app.py` already do, with no pipeline logic duplicated.

### Phase 15 — Conversation-aware query resolution
- [x] `domain/entities.py`: `ConversationTurn`, `ConversationContext` - plain, immutable, same shape rules as `Query`/`Source`
- [x] `application/query_planner.py`: optional `conversation` param on `plan()`, composed into the existing Groq prompt (no second LLM call); cache key folds in a digest of the conversation to prevent cross-conversation collisions
- [x] `config/prompts/query_planner.txt`: reference-resolution instructions + worked example
- [x] `application/pipeline.py`: `handle()`/`handle_streaming()`/`_prepare()` thread the optional `conversation` param through, defaulting to `None`
- [x] `config/settings.py`: `conversation_history_turns` (default 2, `0` disables the feature)
- [x] `presentation/conversation_context.py`: new, pure, unit-tested helper building a windowed `ConversationContext` from Streamlit's `session_state.messages`; wired into `streamlit_app.py`
- [x] 19 new unit tests, all touched files at 100% statement coverage
- [x] Live-verify against real Tavily/Groq: a real 5-question conversation, including a topic switch partway through - see [`docs/phases/phase15.md`](phases/phase15.md)
