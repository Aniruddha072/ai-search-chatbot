# Phase 9 — Caching

**Commit:** `da3324d` (feat(cache): implement InMemoryCache and wire it into planning + search)

## What we built
- `src/infrastructure/cache/memory_cache.py`: `InMemoryCache`, implementing the `Cache` port from Phase 1. A dict of `key -> (value, expires_at)`, `time.monotonic()` for expiry math, lazy expiry checked on `get`. No lock, no size limit, no background sweep - deliberate scope for a single-process, dev-default cache.
- `src/application/query_planner.py`: `QueryPlanner` gained `cache: Cache` and `cache_ttl_seconds: float`. Cache key is the normalized (lowercased, whitespace-collapsed) question. **Only successful plans are cached** - the fallback `Query` built on LLM failure is never written to cache, so a transient failure can't poison future identical requests with a degraded plan.
- `src/application/search_orchestrator.py`: `SearchOrchestrator` gained the same two params, wired into `_search_one`. Cache key is `(normalized sub-query, max_results)` - `max_results` included deliberately, so a cache entry written for one result count can never silently satisfy a request for a different one.
- `src/bootstrap.py`: two **separate** `InMemoryCache()` instances - one for query plans, one for search results - not one shared cache.
- Two new `Settings` fields: `query_plan_cache_ttl_seconds` (600s) and `search_result_cache_ttl_seconds` (3600s), matching the exact numbers decisions.md §7 already committed to.
- Test files: `test_memory_cache.py` (set/get/miss/overwrite/real-short-TTL-expiry/distinct-keys), plus cache-specific additions to `test_query_planner.py` (cache hit skips the LLM, normalization, fallback-not-cached) and `test_search_orchestrator.py` (cache hit skips the provider, `max_results` differentiates keys, normalization). Existing fakes gained call-count tracking to make "was NOT called again" assertable.

## What we learned
- Adding a required constructor param to two already-widely-used classes (`QueryPlanner`, `SearchOrchestrator`) has a real, traceable ripple effect: five files needed updates beyond the two core implementation files (`bootstrap.py`, three unit test files, one integration test file) - all straightforward, but worth naming as the cost of staying consistent with "every collaborator is a required constructor param, no `Optional`-with-`None`-escape-hatch" rather than a hidden surprise.
- A stray `TypeError` in one integration test (from missing the new required args) had a confusing knock-on effect: a *different*, unrelated integration test failed with `assert False` when run as part of the same suite, but passed cleanly in isolation - a reminder that a collection-time/early failure in one test file can produce misleading noise in a sibling test's result within the same run, worth verifying failures in isolation before concluding they're real.
- **A genuinely unrelated finding, incidentally surfaced by re-running the real end-to-end integration test:** Tavily can return a source `url` that isn't absolute - one real run returned `/goto?url=CAESdQ...` (a relative Google-News-style redirect wrapper) instead of `https://...`. Nothing in the pipeline (dedup, rank, context building, citation) currently validates or normalizes URL shape, so it flowed all the way into `Answer.sources` unchanged. This is out of Phase 9's scope entirely - noted here and logged for Phase 10 (resilience/input-output validation is explicitly that phase's job), not fixed now.

## Key design decisions
- Two separate `InMemoryCache` instances, not one shared cache keyed by a prefix - a raw user question could in principle collide with a generated sub-query string; separate instances avoid the wrong-value-type risk by construction rather than by convention.
- `cache` is a required constructor param on both `QueryPlanner` and `SearchOrchestrator`, not `Cache | None = None` - consistent with every other collaborator in this codebase being required, even though it meant updating more call sites than a phase usually touches.
- Fallback query plans are never cached (see "What we built" above) - a deliberate correctness choice, not an oversight, verified with a dedicated test.
- `max_results` is part of the search-result cache key - a one-line addition that closes a real silent-wrong-answer risk for negligible cost.
- No lock, no eviction policy, no size cap on `InMemoryCache` - matches decisions.md's own "fine for a single-process CLI demo" framing; genuinely worth revisiting once Phase 11/14 make the process long-running, at which point the `Cache` port already makes swapping in Redis a config change, not a rewrite.

## Challenges faced
Two integration-test call sites needed updating for the new required constructor args (`tests/integration/test_query_planner.py`), caught immediately by running the gated suite rather than assuming unit tests alone were sufficient. The unrelated Tavily relative-URL finding (above) was investigated and explicitly deferred, not chased into an out-of-scope fix.
