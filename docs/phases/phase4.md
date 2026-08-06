# Phase 4 — Context Building

**Commit:** `6da336b` (feat(context): implement ContextBuilder and TrafilaturaContentExtractor)

## What we built
- `src/domain/interfaces.py`: added the `ContentExtractor` ABC (`async extract(url) -> str | None`) - unlike `Deduplicator` in Phase 3, this one gets an interface because the architecture doc explicitly names a future swap (trafilatura vs. readability).
- `src/infrastructure/content/content_extractor.py`: `TrafilaturaContentExtractor`, wrapping trafilatura's synchronous `fetch_url()`/`extract()` calls in `asyncio.to_thread()` so the event loop isn't blocked.
- `src/utils/token_counter.py`: `count_tokens()`/`truncate_to_token_count()` using a `len(text)//4` character heuristic - not tiktoken (see Decision 4.1).
- `src/application/context_builder.py`: `ContextBuilder` - top-K selection, thin-snippet full-fetch triggering (only for the top few candidates, concurrent via `asyncio.gather(..., return_exceptions=True)` with a per-fetch `asyncio.wait_for` timeout, reusing the exact resilience idiom `SearchOrchestrator` established in Phase 2), then greedy rank-order token-budget enforcement that truncates or drops lower-ranked sources rather than the highest-ranked ones.
- Three new `Settings` fields, each documented in `.env.example`: `context_token_budget` (2500, must be > 1000), `max_context_sources` (6, must be > 0), `content_fetch_timeout_seconds` (10.0, must be > 0) - all validated in `settings.py` via Pydantic `Field(gt=...)`.
- New dependency: `trafilatura`.
- Six test files: `test_token_counter.py`, `test_content_extractor.py` (mocked trafilatura calls), `test_context_builder.py` (top-K, thin-snippet trigger, extraction failure/timeout fallback, token-budget truncation and dropping, citation indexing), plus new cases added to `test_settings.py` for the three new fields' validation bounds.

## What we learned
- Measured, not assumed: `tiktoken.get_encoding("cl100k_base")` took **15.5 seconds** on first call (silently downloading its vocabulary file over the network) and ~0.26s on every call after, since it caches locally. For a project explicitly about minimizing latency, a "lightweight" tokenizer utility with a hidden 15-second cold start and a network dependency was worth measuring before adopting, not just trusting because it's the standard choice.
- `difflib`-style "is this too similar" bugs (Phase 3) have a token-budget-loop analogue: a truncated source's token count must be re-measured after truncation, not assumed to exactly equal the requested budget, because the character-based heuristic can round either direction. The implementation explicitly re-counts `content_used` after truncating rather than trusting `remaining_budget -= max_tokens`.

## Key design decisions
- `ContentExtractor` is a domain interface; `Deduplicator` (Phase 3) is not. The distinguishing test is whether the architecture doc names a real alternative implementation - it explicitly does here (readability vs. trafilatura), it didn't for dedup.
- `ContextBuilder.build()` takes only `list[SearchResult]`, no `Query` - the decisions.md 1.3 trigger "or the query is comparison-heavy" is deliberately not implemented yet, since `Query.complexity` has no defined semantics until Phase 5 exists. Only the snippet-length trigger is implemented now.
- The per-fetch timeout lives in `ContextBuilder`, not `TrafilaturaContentExtractor` - the same separation Decision 2.2 established for `SearchOrchestrator`/`TavilyProvider`, reused rather than re-derived.
- `context_token_budget`, `max_context_sources`, and `content_fetch_timeout_seconds` are `Settings` fields (unlike Phase 3's ranking weights) - they directly control cost/latency/how-much-reaches-the-LLM, the same category Phase 2's `search_timeout_seconds`/`max_search_results` are already in.

## Challenges faced
- None blocking. The token-budget loop needed one self-caught fix during implementation (see What we learned) before it matched the "never exceed the cap" test.
