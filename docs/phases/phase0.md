# Phase 0 — Project Scaffolding

**Commits:** `a94576b` (chore: archive v1 learning prototype), `2e5ff72` (chore: initialize project scaffold)

## What we built
- Archived the earlier LangChain + Gemini + Tavily prototype (a Module 7 learning exercise) into `archive/module7-learning-search-agent/`, unmodified, so it stays available for reference without being mistaken for the active codebase.
- Initialized git, connected a GitHub remote, renamed the default branch to `main`.
- Created the clean-architecture package skeleton from the design doc (`domain/`, `application/`, `infrastructure/{search,llm,evaluation,cache,content}/`, `config/prompts/`, `presentation/`, `utils/`) as empty packages.
- `src/config/settings.py`: a `pydantic-settings` class that loads `TAVILY_API_KEY`/`GROQ_API_KEY` from `.env` and fails fast with one clear error if either is missing or empty.
- `src/utils/logging.py`: structured logging with a `ContextVar`-based turn ID, so concurrent requests can be told apart in log output.
- `LICENSE` (MIT) and a hardened `.gitignore` (build artifacts, coverage reports, editor directories), added after a pre-commit repository review.

## What we learned
- `pydantic-settings` treats an *empty* environment variable as a present, valid string, not a missing one — `Field(..., min_length=1)` was needed to actually reject `GROQ_API_KEY=`.
- `ContextVar` (not a plain module-level global) is the correct primitive for a per-request correlation ID, because async tasks running concurrently via `asyncio.gather` would otherwise stomp on each other's turn ID.

## Key design decisions
- Archive, don't delete, the v1 prototype — it's a legitimate reference point for how the project evolved, and worth keeping visible in a portfolio repo.
- Two separate commits (archive vs. scaffold) rather than one, so `git log`/`git blame` can isolate either change later.
- `.env` kept at the repo root and reused across old and new code rather than duplicated; only the new required key was appended to it.

## Challenges faced
- None blocking; the empty-string validation gap above was caught by deliberately testing the failure path, not by accident.
