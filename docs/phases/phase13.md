# Phase 13 — Observability & Polish

**Commit:** _(pending)_

## What we built
- `src/application/pipeline.py`: `ChatPipeline` now records per-stage wall-clock durations (planning, search, context, generation, eval) via a small `_timed()` helper, and logs one `turn timings: planning=Xs search=Xs context=Xs generation=Xs eval=Xs total=Xs` INFO summary at the true end of every turn - success or any degradation point - reporting whatever stages actually ran. `handle_streaming()`'s "generation" duration spans stream hand-off through full consumption by the caller (there's no single awaitable to wrap the way the other stages are, since token generation happens as the caller iterates), measured inside `PipelineStream.streaming()`'s `finalize()`.
- `src/utils/logging.py`: `configure_logging()`'s handler now targets `stderr` instead of `stdout` - closes the cosmetic log/streamed-answer interleaving gap noted in Phase 11.
- `tests/unit/test_pipeline.py`: 5 new tests asserting the timing summary's stage names appear/don't appear correctly across all four `handle()` outcomes (success, invalid input, zero sources, generation failure) plus `handle_streaming()`'s deferred-until-consumed logging.
- `tests/unit/test_logging.py`: 1 new test asserting the root handler's stream is `sys.stderr`.
- `README.md`: notes the new `turn timings:` log line and that logs land on stderr, separable from the answer text on stdout.

## What we learned
- A real live CLI run with `stdout`/`stderr` captured to separate files confirmed both changes at once: stdout held only the answer/sources/evaluation text with zero log noise, and stderr held every log line including the new `turn timings: planning=0.58s search=2.74s context=0.00s generation=0.36s eval=11.39s total=15.15s` summary.
- That same live run hit Groq's *daily* token quota (100k TPD, separate from the per-minute limits Decision 12.2 dealt with) again mid-session from cumulative testing - the pipeline degraded exactly as designed, a clear `(evaluation unavailable: ...)` message with no crash. Same known external constraint as before, not a new bug - no GitHub issue, no code change.
- `docs/architecture.md` had already named "timing, logging" as a planned `ChatPipeline` responsibility before this phase existed - confirmed as an accurate forward-looking note rather than a deviation once actually implemented, so no rewrite was needed there.

## Key design decisions
See `docs/decisions.md`, Decisions 13.1-13.2, for the full reasoning behind the timing-instrumentation design (especially the streaming-generation measurement approach and the deliberately-accepted mid-stream-failure gap) and the stdout/stderr split.

## Challenges faced
None structural. The only real design question was how to time `handle_streaming()`'s generation stage given that token production happens inside the caller's own iteration loop, not inside a single `ChatPipeline`-controlled awaitable - resolved by timing the full hand-off-to-consumption window instead, documented as a deliberate tradeoff (Decision 13.1) rather than treated as an approximation to apologize for.
