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

## 2026-08-11 – 2026-08-12 — Testing, observability, and a public demo (Phases 12–14)

Fourth working session, spanning into the next day. Closed out the
project's remaining core phases: an audit-driven testing pass, real
per-turn observability, two rounds of direct-feedback UX polish, and a
public Streamlit demo — the project's first externally-facing surface.

**Phases completed:** [12](docs/phases/phase12.md) (testing) ·
[13](docs/phases/phase13.md) (observability & polish) ·
[14](docs/phases/phase14.md) (public Streamlit demo)

**Commits:** `c6d3a7d` → `726c759` (Phases 12–14, 8 commits, pushed).
Full history: `git log --oneline c6d3a7d..726c759`.

**Highlights worth remembering:**
- Phase 12 was an audit, not a rebuild: `pytest-cov` showed every `domain/`/`application/`/`infrastructure/` module already fully covered incidentally, with only 2 real gaps in `ranker.py` and a closeable gap in `cli.py` — both closed with genuinely new tests, not busywork.
- The morning started with a real evaluation failure (`TimeoutError`) reported live — resolved not by touching the evaluator, but by measuring a real successful RAGAS call's own runtime (~14.5s) and finding the 15s budget was simply too tight; raising it to 30s, then getting one real live run to print actual Faithfulness/Context Precision scores end-to-end, closed out Phase 11's evaluation work for good.
- Two rounds of live dogfooding drove Phase 13's real shape, both from direct feedback rather than planning: separating stdout/stderr didn't itself make the CLI *look* clean (logs still shared the terminal by default) until `LOG_LEVEL` defaulted to `CRITICAL`; and even a quiet CLI still leaked raw exception text through two on-purpose messages, fixed to a simple, non-technical, always-actionable tone ("...Please try again **later**." — the word mattered, by explicit request).
- Phase 14 started with a wrong first choice, caught before any code was written: Gradio + Hugging Face Spaces was selected, then ruled out by checking HF's *current* docs live — creating a Gradio Space now needs a paid plan, conflicting with an explicit "no money" requirement. Streamlit Community Cloud, checked the same way, is genuinely free.
- The real engineering surprise of the whole session: a cached pipeline reused across Streamlit reruns crashes on a session's *second* question (`RuntimeError: Event loop is closed`) because async HTTP clients bind to whichever event loop was running when first used, and `asyncio.run()` tears its loop down each time. Reproduced in two lines of isolated `httpx` code before touching the real app, fixed by building a fresh pipeline inside every turn's single `asyncio.run()` call, and verified live through the actual running demo — two real consecutive questions, no crash.
- `st.write_stream()`, the obvious built-in for streaming `PipelineStream`, turned out unusable for two independent reasons found by reading Streamlit's own source: it spins up its own separate event loop internally (the same crash, one level deeper), and it only accepts a real async generator, not `PipelineStream`'s `__aiter__`-based design. Streamed by hand into a placeholder instead.

**State at end of session:** see [`docs/session-handoff.md`](docs/session-handoff.md) (local-only) for exact resume-point details.

---

## 2026-08-13 — First milestone polish, then Phase 15 (conversation memory)

Fifth working session. Split cleanly into two halves: closing out the
project's "first deployed milestone" as a real, polished public
artifact (not just working code), then designing, building, and
shipping conversation-aware follow-up resolution end to end - issue,
design, implementation, live verification, PR, merge, and a real
production incident caught and fixed on the actual deployed demo.

**Phases completed:** [15](docs/phases/phase15.md) (conversation-aware
query resolution)

**Commits:** `6c0006d` → `786d79a` (4 commits, pushed to `main`, the
middle two via PR #4's rebase merge). Full history:
`git log --oneline 6c0006d..786d79a`. Also: git tag/release `v1.0.0`,
GitHub issue #3, and PR #4 (merged, closed #3).

**Highlights worth remembering:**
- Milestone work first: real screenshot of the live demo captured via browser automation (not fabricated) for the README, then a full portfolio-first restructure - Live Demo moved above the fold, a simplified Mermaid pipeline diagram, a fact-grounded Engineering Highlights section, and the Phase 0-14 checklist condensed to one status line with the full source tree/checklist folded into `<details>`. Closed with a `v1.0.0` GitHub Release once the reported "169 unit tests" claim was re-run and freshly confirmed, not just recalled from memory.
- GitHub hygiene, done deliberately rather than reflexively: added an `enhancement` + project-specific `phase-15` label and considered (then declined) building a bigger label taxonomy for a solo repo; the milestone was first named "Phase 15" then renamed to `v1.1.0` on direct feedback that internal phase-numbering doesn't belong in GitHub's own release-facing vocabulary. The Phase 15 branch was created via `gh issue develop` specifically so it would show up in the issue's Development panel automatically, rather than a plain `git branch` that GitHub wouldn't have linked.
- The Phase 15 issue itself was written twice: a first pass mixed the concise problem statement with the full implementation design in one body, then rewritten on request into a short problem/goal/scope/acceptance-criteria issue with the full technical design moved to a separately-labeled first comment - and both were rewritten again after direct feedback that the dash-heavy, bold-label-then-explanation phrasing read as AI-generated rather than human-written.
- The feature itself: `QueryPlanner.plan()` resolves a follow-up's pronouns ("which one", "its") against a bounded sliding window of recent turns, folded into the *existing* Groq call rather than a second rewrite call - zero additional Groq calls per turn, with a cache-key fix for a real (if previously latent) cross-conversation collision bug this surfaced. `conversation_context.py` was split out of `streamlit_app.py` into its own module specifically so it could be unit-tested without executing that file's top-level Streamlit calls.
- Live-verified, not just unit-tested: the real 5-question conversation from the design proposal, run against real Tavily/Groq. Every turn resolved correctly, including a genuine surprise on turn 4 ("What about VIT?") - with only 2 turns of window by then, the real model produced a sensible COEP-vs-VIT comparison across whatever was actually still in the window, rather than the narrower behavior the original hypothetical walkthrough had assumed.
- A requested diagram went through two drafts: an ASCII-art sliding-window picture was rejected on sight for alignment/font fragility, redone as a real Mermaid diagram (matching the existing pipeline diagram's color scheme) embedded in both the README and the new `docs/phases/phase15.md` build log.
- PR #4 merged via `--rebase` rather than a merge commit, specifically to keep `main`'s history linear (matching every prior phase, which was pushed directly with no merge commits) while still preserving the feat/docs commit split as two distinct commits.
- A real post-merge incident, caught only by actually checking the redeployed live demo rather than assuming the merge was the finish line: `ImportError: cannot import name 'ConversationContext'` on Streamlit Community Cloud immediately after redeploy. Diagnosed by directly diffing GitHub's own `main` branch content (not just trusting the local checkout) to rule out a bad merge first - confirmed the shipped code was correct, so the culprit was Streamlit Cloud reusing a stale in-memory module from before the redeploy rather than a real bug. Fixed with a manual app reboot (the user's own action, not something done on their behalf), then re-verified live: the exact "which one is cheapest?" question that used to derail into sports-team trivia now correctly compares real college fees, in production.

**State at end of session:** see [`docs/session-handoff.md`](docs/session-handoff.md) (local-only) for exact resume-point details.

---

## 2026-08-17 — Groq model migration ahead of the Aug 16 deprecation deadline

Short maintenance session, not tied to a roadmap phase. Groq announced
`llama-3.1-8b-instant` and `llama-3.3-70b-versatile` (used as
`groq_fast_model`/`groq_capable_model`) would be decommissioned August 16,
2026; migrated both to Groq's own recommended replacements before the
deadline.

**Commits:** `0f7462b` (`fix: migrate off Groq models deprecated for Aug
16, 2026 shutdown`), merged to `main` via PR #5 (`--rebase`).

**Highlights worth remembering:**
- Verified the deprecation and the recommended replacements directly against Groq's own docs page rather than trusting the claim secondhand: `openai/gpt-oss-20b` replaces `llama-3.1-8b-instant`, `openai/gpt-oss-120b` replaces `llama-3.3-70b-versatile`.
- Scoped the edit precisely: live code, tests, and `.env.example` updated; historical mentions in `docs/decisions.md`'s existing entries and the Phase 5/6/12 build logs left untouched on purpose, since they're dated records of what was true about the old models at the time.
- Verified live against the real Groq API before trusting the swap - both `generate_structured()` and `generate_stream()` worked cleanly on the new models with no schema or streaming differences from before, worth checking given this project had already hit one real structured-output incompatibility switching *to* the old models originally (Decision 1.5's phase log).
- Also ran a real RAGAS evaluation against `openai/gpt-oss-120b` out of curiosity about the public demo's `NullEvaluator` tradeoff (Decision 14.2) - latency came back at ~14.6s, essentially unchanged from the old model, so the migration doesn't change that calculus.
- Documented as Decision 16.1 rather than a new phase - this was maintenance forced by an external deprecation schedule, not new functionality.

**State at end of session:** merged to `main`, live demo redeployed on the new models.

---

## 2026-08-20 — A live-demo bug report that turned out not to be a bug

Investigated a real user-reported failure on the live demo: a follow-up
question ("What about COEP?" right after asking about a different,
similarly-named college) came back with a refusal and no sources, right
after the Aug 17 Groq migration went live. Spent the session tracking
down which of three possible causes was responsible before touching any
code.

**Commits:** `4314905` (`docs: record COEP follow-up investigation as
stale-deploy state, not a planner bug`), merged to `main`.

**Highlights worth remembering:**
- Found and flagged a real gap along the way: `cli.py`'s `_handle_turn()` never threads `ConversationContext` between turns at all, unlike `streamlit_app.py` - meaning a literal CLI reproduction wouldn't have exercised the same code path as the actual live failure. Reproduced instead through `build_demo_pipeline()` directly with a manually built `ConversationContext` matching what production builds.
- Added temporary debug logging at two points in `ChatPipeline._prepare()` (post-planning sub-queries, pre-generation source list) specifically to distinguish three failure modes: the planner falling back after an internal error, the planner resolving the follow-up badly, or the planner and retrieval both working while generation refused anyway.
- 7 live reproduction attempts (4 with conversation context, 3 as a no-context control) all succeeded - the reported failure never reproduced locally, and none of the three hypothesized causes ever showed up.
- Rebooting the live app and re-running the exact reported question sequence twice more, directly against the live demo, also succeeded both times - pointing to stale per-process state left over from the migration's redeploy rather than a defect in the query planner or generation prompts, the same class of issue as a real incident from Phase 15 (`ImportError` after merge, fixed by a manual reboot).
- No prompt files were touched, since nothing pointed at the actual planning or generation logic being wrong. Documented as Decision 16.2; debug logging was removed before committing.

**State at end of session:** merged to `main`. Operational lesson going forward: reboot the Streamlit app after every redeploy, not just when something visibly throws.

---
