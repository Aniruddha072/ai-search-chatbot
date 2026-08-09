# Roadmap & Task Checklist

Related docs: [Architecture](architecture.md) · [Decisions & tradeoffs](decisions.md) · [Phase build logs](phases/)

Each phase produces something runnable/testable before moving on — no phase
depends on an unbuilt future phase. Current status is tracked in the
[root README](../README.md#current-progress); a build log for each completed
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

**Phase 14 — Optional: FastAPI layer**
`api.py` wrapping the same `ChatPipeline`, only after everything above is solid.

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
- [x] `infrastructure/llm/groq_client.py`: generation method using the capable model (non-streaming; streaming deferred to Phase 11 - no real consumer exists yet)
- [x] `application/answer_generator.py`: build indexed source list, call Groq, parse citation markers into `Answer`
- [x] Unit tests: mocked Groq output with citations mapped back to correct `Source` objects

### Phase 7 — Pipeline wiring
- [x] `application/pipeline.py`: `ChatPipeline.handle(user_query) -> Answer` composing phases 2–6
- [x] `bootstrap.py`: composition root wiring concrete providers from settings into `ChatPipeline`
- [x] Manual end-to-end smoke test with a real question (made automated/repeatable as a gated integration test rather than a one-off script)

### Phase 8 — RAGAS evaluation
- [ ] `infrastructure/evaluation/ragas_evaluator.py`: implement `Evaluator`, wrap RAGAS with Groq as judge LLM
- [ ] Wire faithfulness, answer_relevancy, context_precision as concurrent metric calls
- [ ] `application/evaluation_service.py`: non-blocking wrapper — catches evaluator errors, returns `None` on failure
- [ ] Wire into `ChatPipeline` as the final step
- [ ] Unit test: evaluator failure does not propagate to pipeline failure

### Phase 9 — Caching
- [ ] `infrastructure/cache/memory_cache.py`: TTL dict-based `Cache` implementation
- [ ] Wire query-plan caching into `QueryPlanner`
- [ ] Wire per-sub-query result caching into `SearchOrchestrator`
- [ ] Unit tests: cache hit skips the underlying call (assert mock not called twice)

### Phase 10 — Resilience hardening
- [ ] Add `tenacity` retry decorators to Tavily and Groq client calls
- [ ] Define typed exceptions: `SearchProviderError`, `LLMGenerationError`, `EvaluationError`
- [ ] Catch and translate exceptions at `ChatPipeline` boundary into a single response shape
- [ ] Implement the degradation ladder from [decisions.md, Error Handling Strategy](decisions.md#6-error-handling-strategy) (all-search-failed path, generation-failed path)
- [ ] Input validation at pipeline entry (empty/oversized query rejection)

### Phase 11 — CLI presentation
- [ ] `presentation/cli.py`: interactive loop reading stdin, calling `ChatPipeline`
- [ ] Stream answer tokens to stdout as they arrive
- [ ] Print sources and RAGAS scores after the answer
- [ ] Handle Ctrl-C / empty input gracefully

### Phase 12 — Testing
- [ ] Unit test coverage for every `application/` module (providers/LLM mocked)
- [ ] Integration test suite behind `RUN_INTEGRATION_TESTS=1` env flag
- [ ] At least one full end-to-end integration test with real Tavily + Groq

### Phase 13 — Observability & polish
- [ ] Per-stage timing captured and logged per turn (planning/search/context/generation/eval durations)
- [ ] README: setup instructions, architecture summary, how to run
- [ ] Finalize architecture.md/decisions.md with any deviations made during implementation

### Phase 14 — Optional: FastAPI layer
- [ ] `presentation/api.py`: single `POST /chat` endpoint calling the same `ChatPipeline`
- [ ] Request/response Pydantic models
- [ ] SSE or WebSocket streaming variant (optional stretch)
