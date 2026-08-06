# Phase 3 — Dedup + Ranking

**Commit:** `be12c7f` (feat(ranking): implement Deduplicator and HeuristicRanker)

## What we built
- `src/application/deduplicator.py`: `Deduplicator` — a concrete class (no interface, unlike `Ranker`/`SearchProvider`; see Decision 3.1), running two passes: URL normalization (lowercase scheme/host, strip query string/fragment/trailing slash, first-seen wins) then near-duplicate content detection (`difflib.SequenceMatcher` on `title + snippet`, configurable similarity threshold, default 0.85).
- `src/application/ranker.py`: `HeuristicRanker`, implementing the `Ranker` port defined back in Phase 1. Scores each result as a weighted sum of Tavily's own provider score (0.5), keyword overlap against the *original* (pre-decomposition) query (0.35), and a recency decay based on `published_date` when present, neutral (0.5) otherwise (0.15).
- `tests/unit/test_deduplicator.py` and `tests/unit/test_ranker.py`: fixture-based unit tests covering exact-URL dedup, URL-variant normalization, near-duplicate content collapsing, distinct-content survival, keyword/provider/recency ranking order, and graceful handling of missing/unparseable `published_date`.

## What we learned
- `difflib.SequenceMatcher.ratio()` operates at the character level, not the word level — two short strings that share most of their characters (e.g. `"...content one"` vs `"...content two"`) score far more similar than they "should" intuitively. A deduplication test fixture needs genuinely distinct text (different topics entirely), not just a changed trailing word, or it produces a false failure that looks like a code bug but is actually a fixture problem.
- `datetime.fromisoformat` (Python 3.11+) accepts the common ISO 8601 forms search APIs tend to return, but wrapping it in `try/except ValueError` is still necessary — not every provider's date string is guaranteed parseable, and a ranking component should never crash on a single result's malformed metadata.

## Key design decisions
- `Deduplicator` has no ABC/interface — unlike `SearchProvider`, `LLMProvider`, `Ranker`, `Evaluator`, and `Cache`, there's no second deduplication strategy this project plans to swap in later. An interface with only one implementation ever planned is an abstraction paying for a flexibility nobody asked for.
- Dedup similarity threshold and the three ranking weights are constructor-default constants, not `Settings` fields — they're internal scoring heuristics, not ops-level configuration, and there's no evidence yet (that's literally what Phase 8's RAGAS scores are for) about what values are actually better.
- Keyword overlap uses plain token-set overlap, not TF-IDF — TF-IDF needs a document corpus to compute meaningful inverse-document-frequency, and ~10-20 results per query isn't one.
- Ranking is scored against the *original* user query, not the sub-query that produced a given result — matches the `Ranker.rank(results, original_query)` signature already fixed in Phase 1.

## Challenges faced
- One test failure during implementation (`test_different_paths_are_not_deduplicated`) turned out to be the fixture-similarity gotcha described above, not a `Deduplicator` bug — fixed by using clearly unrelated fixture text instead of near-identical sentences with one word changed.
