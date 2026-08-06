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
