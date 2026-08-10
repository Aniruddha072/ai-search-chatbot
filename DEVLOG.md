# Dev Log

A chronological, per-session journal — what happened in each sitting, at a
glance. This is distinct from [`docs/phases/`](docs/phases/): those are
detailed technical write-ups per *phase* (what was built, learned, decided,
the commit hash); this is a lighter running diary per *session*, since one
sitting can span several phases (or a phase can span several sittings).
For full technical detail on any phase mentioned below, follow the link.

---

## 2026-08-06 — Project kickoff through Phase 5 (query planning)

One long working session, 14:25–22:45. Went from an empty repo (plus an
archived v1 learning prototype) to a working, tested pipeline stage that
takes a raw question all the way to a validated, planned `Query` — dedup,
ranking, context building, and Groq-backed query planning all done.

**Phases completed:** [0](docs/phases/phase0.md) (scaffolding) ·
[1](docs/phases/phase1.md) (domain entities/interfaces) ·
[2](docs/phases/phase2.md) (Tavily search integration) ·
[3](docs/phases/phase3.md) (dedup + ranking) ·
[4](docs/phases/phase4.md) (context building) ·
[5](docs/phases/phase5.md) (Groq query planning)

**Commits:** `a94576b` → `26192a2` (13 commits, all pushed to
`origin/main`). Full history: `git log --oneline a94576b..26192a2`.

**Highlights worth remembering:**
- Archived the earlier LangChain/Gemini prototype rather than deleting it; rebuilt clean-architecture from scratch.
- Split the original single architecture doc into `docs/architecture.md` / `decisions.md` / `roadmap.md` / `phases/`, and started dating real "Implemented Decisions" alongside the forward-looking ones (`decisions.md` §0).
- Two real API-behavior discoveries that changed the design, not just guesses: `tiktoken` costs 15.5s on first use (network fetch) → used a char-based heuristic instead; Groq's strict `json_schema` mode isn't supported by the models this project committed to → kept them anyway, using `json_object` mode + a hand-written prompt, verified 3/3 against the live API.
- Test suite grew from 0 to 86 unit tests (+ 2 gated real-API integration tests), all green.

**State at end of session:** see [`docs/session-handoff.md`](docs/session-handoff.md) (local-only) for exact resume-point details.

---

## 2026-08-09 — Answer generation through caching (Phases 6–9)

Second working session, 16:34–23:51. Took the pipeline from "plans and
searches" to a fully wired, cached, RAGAS-scored end-to-end system:
generation, evaluation, pipeline composition, and caching all landed.

**Phases completed:** [6](docs/phases/phase6.md) (answer generation) ·
[7](docs/phases/phase7.md) (pipeline wiring) ·
[8](docs/phases/phase8.md) (RAGAS evaluation) ·
[9](docs/phases/phase9.md) (caching)

**Commits:** `b959910` → `d1b2d7b` (10 commits). Full history:
`git log --oneline b959910..d1b2d7b`.

**Highlights worth remembering:**
- First fully real end-to-end run succeeded in Phase 7 — search, planning, generation, and (once Phase 8 landed) RAGAS scoring, all chained through one real `ChatPipeline.handle()` call against live Tavily/Groq APIs.
- Phase 8 was the most eventful phase yet: four unrelated real blockers (a C-extension dependency with no Windows wheel, an import bug present in `ragas`'s *newest* release too, an `isinstance` rejection despite "OpenAI-compatible" SDKs, and a metric cut because Groq has no embeddings model) — all resolved by installing/reading/calling the real thing, documented as Decisions 8.1–8.5.
- Mid-session detour: reproduced (and then honestly failed to reproduce) the Phase 5 JSON-schema-echo bug on request, for a screenshot. 0/20 on the exact original setup — the historical behavior no longer reproduces against the current Groq endpoint, most likely because the hosted model shifted under the same name. Reported as a real negative result, not forced.
- Caught and fixed a real dating error while writing this entry: Decisions 6.1–8.5 had all inherited the previous session's date (2026-08-06) instead of when they actually happened (2026-08-09) — corrected by cross-checking real commit timestamps rather than assuming.
- Incidentally found, not fixed: a real gated run returned a Tavily source with a relative `/goto?url=...` link instead of an absolute URL. Logged for Phase 10 rather than chased mid-Phase-9.

**State at end of session:** see [`docs/session-handoff.md`](docs/session-handoff.md) (local-only) for exact resume-point details.

---

## 2026-08-10 — Resilience hardening through CLI, then two real bugs (Phases 10–11)

Third working session, 12:57–20:32. Took the pipeline from "works but fragile" to "resilient and actually talkable-to": retries, typed exceptions, and graceful degradation landed in Phase 10, then a real interactive streaming CLI in Phase 11 — the first time this project could be used by a human typing a question, not just exercised by tests. Dogfooding that CLI immediately surfaced two real bugs, both taken through a brand-new discover → issue → fix → verify → close workflow adopted mid-session.

**Phases completed:** [10](docs/phases/phase10.md) (resilience hardening) · [11](docs/phases/phase11.md) (CLI presentation)

**Commits:** `19300f9` → `3727303` (7 commits). Full history: `git log --oneline 19300f9..3727303`.

**Highlights worth remembering:**
- Phase 10: typed exception hierarchy (`SearchProviderError`/`LLMGenerationError`/`EvaluationError`), `tenacity` retries targeting only exception sets verified against real Groq/Tavily SDK source (not guessed), and a full graceful-degradation ladder so `ChatPipeline.handle()` never raises. Also closed the Phase 9-deferred Tavily relative-URL finding.
- Phase 11: streaming answers token-by-token via a new `StreamedAnswer` wrapper — verified first that an async generator can't itself `return` a value (a real `SyntaxError`), which is exactly why a wrapper object was needed instead of a bare generator. Manually smoke-tested the real CLI end-to-end against live APIs before calling it done.
- **New standing project workflow, adopted this session:** discover → reproduce → decide if it's worth tracking → GitHub issue (before fixing) → fix → regression test → verify → commit (referencing the issue) → close. Installed and authenticated GitHub CLI (`gh`) for the first time to support it.
- **Bug 1:** a RAGAS evaluation timeout raised a bare `TimeoutError()` whose `str()` is `''` (verified directly) — that blank string was falsy, so both the log line and the CLI's `if evaluation.error:` check silently treated a real failure as if none occurred. Fixed with a type-name fallback plus an `is not None` check instead of truthiness. Verified via an isolated script driving the real `ChatPipeline`/CLI wiring with zero network calls, since the Groq account was mid-incident on its own rate limit when this was found.
- **Bug 2:** Ctrl-C at the CLI prompt crashed with a raw `KeyboardInterrupt`/`CancelledError` traceback. Root-caused precisely from a real production traceback: `asyncio.run()` cancels the running task (delivering `CancelledError`, not `KeyboardInterrupt`, into whatever it was awaiting) and then re-raises the real `KeyboardInterrupt` from its own top-level frame, after `main()` has already been torn down — no try/except placed anywhere inside `main()`'s coroutine could ever catch that. 14 automated repro attempts (piped stdin, then a genuine new Win32 console with real `CTRL_C_EVENT` delivery) never triggered the race, which turned out to be expected — a real idle terminal prompt is exactly the condition most likely to hit it, and the fix was verified conclusively via a deterministic regression test plus the user's own live Ctrl-C confirmation, not via forcing the race itself.
- Github issue #1 (an overly-detailed first draft) was superseded by the shortened, actually-used #2 - both closed, #1 kept open-turned-closed as the original investigation record rather than deleted.
- Groq's daily token quota (100k) ran out entirely mid-session from live dogfooding - several verification steps had to route around it (isolated no-network scripts, mocked regression tests, one deliberately-deferred live re-test) rather than spend what was left chasing it.

**State at end of session:** see [`docs/session-handoff.md`](docs/session-handoff.md) (local-only) for exact resume-point details.

---
