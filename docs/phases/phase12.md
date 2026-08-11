# Phase 12 — Testing

**Commit:** _(pending)_

## What we built
- `pyproject.toml`: added `pytest-cov` as a real dev dependency, and used it (`pytest --cov=src --cov-report=term-missing`) to audit actual statement coverage before deciding scope, instead of assuming "a test file exists per module" already meant the module was covered.
- `tests/unit/test_ranker.py`: 2 new tests closing the only 2 uncovered branches in `application/`: `test_query_with_no_alphanumeric_tokens_does_not_divide_by_zero` (the keyword-overlap divide-by-zero guard) and `test_future_published_date_ranks_above_an_older_result` (the future-published-date recency branch).
- `tests/unit/test_cli.py`: 4 new tests closing the closeable part of `presentation/cli.py`'s gap - `_print_sources` with no sources, `_read_line` via a monkeypatched `input`, and `_handle_turn`'s happy path plus its mid-stream-exception path, using a small duck-typed `_FakeStream`/`_FakePipeline` pair instead of the real `ChatPipeline`. The file's docstring, which previously claimed none of `cli.py` was unit-testable in isolation, was corrected.
- Re-ran the gated integration suite live (`RUN_INTEGRATION_TESTS=1`, 7/7 passed), including a real `test_real_ragas_evaluator_scores_a_grounded_answer` success - valid Faithfulness/ContextPrecision scores, `error is None`, ~14.5s runtime.
- `docs/roadmap.md`: Phase 12 checklist marked complete.

## What we learned
- Measuring coverage instead of assuming it turned "which tests should we add" from a guess into a checklist: every `domain/`, `application/`, and `infrastructure/` module was already at 100% incidentally, but `ranker.py` had 2 real untested branches and `cli.py` had a meaningful closeable gap beyond its accepted interactive-only surface.
- `_read_line`, `_print_sources`, and `_handle_turn` all take their dependencies (`input`, an `Answer`, a pipeline/stream) as parameters or via `builtins.input`, so none of them actually needed real stdin or process interaction to test - only `main()`'s own loop (owns `build_chat_pipeline()`/`get_settings()` wiring) and the `if __name__ == "__main__":` guard genuinely do, and those stay manual-smoke-test-only, consistent with how `run()`'s Ctrl-C path was already verified in Phase 11 (Decision 11.6).
- The real live RAGAS integration test's ~14.5s runtime, close to `evaluation_timeout_seconds`'s 15s budget even with zero rate-limit retries, explains this morning's live CLI timeouts: RAGAS evaluation is inherently near-budget on this account/model, so any `429` backoff on top reliably exceeds it. Confirmed as an external rate-limit/timeout-margin reality, not a code bug - no evaluation implementation changes made.

## Key design decisions
See `docs/decisions.md`, Decision 12.1, for the full reasoning behind adding coverage tooling and what it changed about scope.

## Challenges faced
None structural - this was an audit-and-close-real-gaps phase, not a rebuild, exactly as anticipated when the phase was scoped. The two ranker.py test bugs caught during writing (a same-day-vs-future tie that never actually hit the target branch, and a `raise_after` index that never fired because the chunk list was too short) were both caught by running the tests, not assumed correct - worth noting since both looked right on first read.
