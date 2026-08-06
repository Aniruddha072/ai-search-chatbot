# Phase 2 — Search Integration

**Commit:** `4bed863` (feat(search): implement Tavily provider and search orchestrator)

## What we built
- `src/infrastructure/search/tavily_provider.py`: `TavilyProvider`, implementing `SearchProvider` via Tavily's `AsyncTavilyClient`. Maps Tavily's raw response fields (`url`, `title`, `content`, `score`, `published_date`) onto `SearchResult` - the only place in the codebase that knows Tavily's field names.
- `src/application/search_orchestrator.py`: `SearchOrchestrator`, which fans a `Query`'s sub-queries out concurrently to any `SearchProvider` via `asyncio.gather(..., return_exceptions=True)`, with a per-query `asyncio.wait_for` timeout. Pure mechanism: a failed or timed-out sub-query is logged and dropped, and even total failure returns an empty list rather than raising - deciding what "no results" means to the user is left to the pipeline (a later phase), not this class.
- Two new `Settings` fields: `search_timeout_seconds` (default 10.0) and `max_search_results` (default 5).
- New dependency: `tavily-python`.
- Three test files: `test_tavily_provider.py` (mocked Tavily client, verifies field mapping), `test_search_orchestrator.py` (fake `SearchProvider`, verifies partial failure, timeout, and real concurrency via elapsed-time assertion), and a gated `tests/integration/test_tavily_search.py` (real Tavily call, opt-in via `RUN_INTEGRATION_TESTS=1`).

## What we learned
- Tavily's real response shape (verified with one live call before writing the adapter, rather than guessing): `results[].{url, title, content, score, raw_content, id}` - no `published_date` in general-topic search, only in news-topic search, so it's read defensively via `.get()`.
- `asyncio.gather(*tasks, return_exceptions=True)` turns *any* exception - a `TimeoutError` from `asyncio.wait_for`, a network error, anything - into a captured value in the results list instead of propagating and cancelling the whole batch. One flag handles every failure mode uniformly; no per-exception-type `try/except` needed.
- A test that asserts on elapsed wall-clock time (`test_queries_run_concurrently_not_sequentially`) is what actually proves concurrency happened, rather than just proving the code runs without erroring.

## Key design decisions
- Two separate classes, not one: `TavilyProvider` only knows how to talk to Tavily; `SearchOrchestrator` only knows how to run N calls against *some* `SearchProvider` concurrently with resilience. Swapping Tavily for another provider later touches zero lines of `SearchOrchestrator`.
- `SearchOrchestrator.search_all()` takes the domain `Query` entity, not a plain `list[str]` - reuses the 1-5 sub-query invariant `Query` already enforces, and the signature documents that this runs right after planning.
- Timeout is enforced by the orchestrator (`asyncio.wait_for`), not trusted to the provider - even if a future provider's SDK has no timeout of its own, the orchestrator's bound always applies.
- No custom exception types yet (`SearchProviderError` etc.) - that's explicitly Phase 10's job. Whatever exception a provider raises natively is enough for now.

## Challenges faced
- The integration test initially failed - not from a `TavilyProvider` bug, but because it called `get_settings()`, which validates the *entire* app config including `GROQ_API_KEY` (still empty; Groq isn't needed until Phase 5/6). Fixed by reading `TAVILY_API_KEY` directly via `python-dotenv` instead of going through the full `Settings` object, so this test only depends on what it actually tests.
