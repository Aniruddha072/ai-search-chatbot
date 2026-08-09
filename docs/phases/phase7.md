# Phase 7 — Pipeline Wiring

**Commit:** `ad28d58` (feat(pipeline): wire ChatPipeline and add the bootstrap composition root)

## What we built
- `src/application/pipeline.py`: `ChatPipeline.handle(user_query) -> Answer`, chaining `QueryPlanner` → `SearchOrchestrator` → `Deduplicator` → `Ranker` → `ContextBuilder` → `AnswerGenerator`. Happy-path only, deliberately - no try/except, no degradation ladder (both explicitly Phase 10 checklist items).
- `src/bootstrap.py`: `build_chat_pipeline()`, the composition root - the one place concrete infrastructure classes get constructed and wired together from `Settings`. Notably, one `GroqClient` instance is shared between `QueryPlanner` and `AnswerGenerator`.
- No new `Settings` fields - everything `bootstrap.py` needed already existed from Phases 2-6.
- Four test files/additions: `test_pipeline.py` (real `SearchOrchestrator`/`Deduplicator`/`HeuristicRanker`/`ContextBuilder`/`QueryPlanner`/`AnswerGenerator`, faked only at `SearchProvider`/`LLMProvider`/`ContentExtractor` - the true I/O boundary), `test_bootstrap.py` (construction succeeds; the shared-`GroqClient` property is directly asserted, not just claimed in a comment), and a gated `tests/integration/test_pipeline.py` - the first fully real end-to-end run of the whole system.

## What we learned
- The "reused async HTTP clients" performance optimization from decisions.md §3 required zero new code to realize - it fell out entirely from correct dependency wiring at the composition root (constructing one `GroqClient` and passing the same instance to both `QueryPlanner` and `AnswerGenerator`). Good architecture sometimes means a claimed optimization is really just "don't make the mistake of wiring it wrong."
- Faking only at the true I/O boundary (Option B from the design discussion) caught something a fully-mocked test wouldn't have: the query-planner-fallback test proves the fallback `Query`'s single sub-query (the raw question text) genuinely round-trips through the real `SearchOrchestrator` into a real `FakeSearchProvider` lookup keyed on that exact text - a fully-mocked `ChatPipeline` test would have hidden this data-shape dependency entirely.
- Even without Phase 10's explicit degradation ladder, the system already degrades reasonably when search finds nothing: empty results flow through dedup/rank/context-building untouched, and `AnswerGenerator`'s Phase 6 cite-or-refuse prompt correctly says it lacks information rather than crashing or hallucinating. Verified with both a fake-provider unit test and implicitly available in the real end-to-end path too.

## Key design decisions
- `ChatPipeline` depends on `Ranker` (the one true port among its six collaborators) but on the concrete `QueryPlanner`/`SearchOrchestrator`/`Deduplicator`/`ContextBuilder`/`AnswerGenerator` classes directly - matching the architecture doc's component table, where only `Ranker` has a named future alternative among these six.
- `build_chat_pipeline()` is a plain function, not `@lru_cache`-wrapped like `get_settings()` - it has exactly one natural call site per process (a future CLI's startup), so there's nothing to memoize; the caller holds the single `ChatPipeline` instance.
- Error handling and the degradation ladder are explicitly out of scope for this phase, per the roadmap's own phase boundaries (Phase 10) - `ChatPipeline.handle()` lets `AnswerGenerator`'s propagated failures (Decision 6.1) bubble straight out uncaught.

## Challenges faced
- None blocking. This phase was pure composition of already-verified pieces - the first phase with no live-API surprise to design around, since nothing new was being integrated.
